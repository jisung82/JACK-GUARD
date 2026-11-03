import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import psutil
import pytest

from jack_guard.config.store import Settings, Store, validate
from jack_guard.core.hotkeys import Hotkeys, parse_hotkey
from jack_guard.core.process_monitor import ProcessMonitor, normalized, safe_target
from jack_guard.core.windows_lock import lock_workstation
from jack_guard.logging.events import Events
from jack_guard.security.passwords import hash_password, valid_record, verify_password


def test_lock_api_success_and_failure():
    api = Mock(return_value=1)
    lock_workstation(api)
    api.assert_called_once_with()
    with pytest.raises(OSError):
        lock_workstation(lambda: 0)


def test_password_salted_and_constant_format():
    first, second = hash_password("correct horse"), hash_password("correct horse")
    assert first != second
    assert verify_password("correct horse", first)
    assert not verify_password("wrong", first)
    assert "correct horse" not in json.dumps(first)
    assert not valid_record({"iterations": 10**12})
    assert not verify_password("x", {"salt": "bad"})
    with pytest.raises(ValueError):
        hash_password("short")


@pytest.mark.parametrize("text", ["L", "Ctrl+Ctrl+L", "Ctrl+F25", "Ctrl+ä", "X+L", 5])
def test_hotkey_validation(text):
    with pytest.raises(ValueError):
        parse_hotkey(text)


def test_hotkey_conflict_cleans_partial_registration():
    api = Mock()
    api.RegisterHotKey.side_effect = [1, 0]
    keys = Hotkeys([lambda: None, lambda: None], api)
    with pytest.raises(OSError):
        keys.register(["Ctrl+Alt+L", "Ctrl+Alt+P"])
    assert keys.registered == []
    api.UnregisterHotKey.assert_called_once_with(None, 1)


def test_hotkey_cleanup():
    api = Mock()
    keys = Hotkeys([], api)
    keys.register(["Ctrl+Alt+L", "Ctrl+Alt+P"])
    assert keys.registered == [1, 2]
    keys.close()
    assert api.UnregisterHotKey.call_count == 2


@pytest.mark.parametrize("code, message", [(1409, "충돌"), (5, "접근 거부")])
def test_hotkey_error_distinguishes_collision_from_access_denied(code, message):
    import ctypes

    def fail(*args):
        ctypes.set_last_error(code)
        return 0

    api = Mock()
    api.RegisterHotKey.side_effect = fail
    keys = Hotkeys([], api)
    with pytest.raises(OSError, match=message):
        keys.register(["Ctrl+Alt+L"])
    assert not keys.registered


def test_config_roundtrip_acl_and_export(tmp_path):
    store = Store(tmp_path / "data")
    value = Settings(password=hash_password("some secret"), terminate=True)
    store.save(value)
    assert store.load() == value
    exported = tmp_path / "export.json"
    store.export(value, exported)
    assert json.loads(exported.read_text())["password"] == {}
    imported = store.import_file(exported, value.password)
    assert imported.password == value.password
    assert not imported.terminate and not imported.monitor
    assert not store.path.with_suffix(".tmp").exists()


def test_config_corruption_does_not_bypass_password(tmp_path):
    store = Store(tmp_path)
    store.path.write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError, match="reset-settings"):
        store.load()
    assert store.recovered


@pytest.mark.parametrize(
    "changes",
    [
        {"monitor": "true"},
        {"games": ["foo.exe"]},
        {"retention_days": False},
        {"password": {"salt": "x"}},
        {"lock_hotkey": "Ctrl+Alt+P"},
        {"unknown": True},
    ],
)
def test_invalid_settings(changes):
    value = asdict(Settings()) | changes
    with pytest.raises(ValueError):
        validate(value)


def process(pid, path, creation=1):
    return SimpleNamespace(info={"pid": pid, "exe": str(path), "create_time": creation})


def test_monitor_full_path_exceptions_dedup_and_pid_reuse(tmp_path):
    path = tmp_path / "game.exe"
    value = Settings(monitor=True, games=[str(path)])
    monitor = ProcessMonitor()
    assert monitor.scan(value, [process(500, tmp_path / "other" / "game.exe")]) == []
    assert len(monitor.scan(value, [process(500, path)])) == 1
    assert monitor.scan(value, [process(500, path)]) == []
    assert len(monitor.scan(value, [process(500, path, 2)])) == 1
    value.exceptions = [str(path)]
    assert monitor.scan(value, [process(501, path)]) == []
    value.monitor = False
    assert monitor.scan(value, [process(502, path)]) == []


def test_monitor_default_does_not_terminate(tmp_path, monkeypatch):
    terminate = Mock()
    monkeypatch.setattr("jack_guard.security.windows.terminate_owned", terminate)
    value = Settings(monitor=True, games=[str(tmp_path / "game.exe")])
    ProcessMonitor().scan(value, [process(500, value.games[0])])
    terminate.assert_not_called()


def test_monitor_denied_and_failed_termination(tmp_path, monkeypatch):
    terminate = Mock(side_effect=PermissionError)
    monkeypatch.setattr("jack_guard.security.windows.terminate_owned", terminate)
    path = str(tmp_path / "game.exe")
    value = Settings(monitor=True, games=[path], terminate=True)
    event = ProcessMonitor().scan(value, [process(os.getpid(), path)])[0]
    assert "보호 대상" in event["action"]
    terminate.assert_not_called()
    monkeypatch.setattr("jack_guard.core.process_monitor.safe_target", lambda *a: True)
    event = ProcessMonitor().scan(value, [process(9999, path)])[0]
    assert "권한" in event["action"]


def test_essential_process_and_parent_protection():
    assert not safe_target(os.getpid(), sys.executable)
    assert not safe_target(os.getppid(), sys.executable)
    assert not safe_target(9999, r"C:\Windows\System32\notepad.exe")
    assert not safe_target(9999, r"C:\games\lsass.exe")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process handle integration")
def test_native_owned_child_termination_and_path_mismatch():
    from jack_guard.security.windows import terminate_owned

    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], creationflags=0x08000000
    )
    try:
        with pytest.raises(PermissionError):
            terminate_owned(child.pid, str(Path(sys.executable).with_name("different.exe")))
        assert child.poll() is None
        terminate_owned(child.pid, normalized(sys.executable))
        child.wait(timeout=5)
        assert child.returncode == 1
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_logs_retention_deletion_and_volume_bound(tmp_path):
    (tmp_path / "events-2000-01-01.jsonl").write_text("old")
    events = Events(tmp_path, retention=1)
    assert not (tmp_path / "events-2000-01-01.jsonl").exists()
    events.add("start", "test")
    assert '"start"' in events.read()
    assert "test" in events.read()
    events.clear()
    assert events.read() == ""


def test_startup_registry_roundtrip():
    from jack_guard.core.startup import is_enabled, set_enabled

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Registry:
        HKEY_CURRENT_USER, REG_SZ = 1, 1
        value = None

        def CreateKey(self, *args):
            return Key()

        OpenKey = CreateKey

        def SetValueEx(self, key, name, zero, kind, value):
            self.value = value

        def DeleteValue(self, *args):
            if self.value is None:
                raise FileNotFoundError
            self.value = None

        def QueryValueEx(self, *args):
            if self.value is None:
                raise FileNotFoundError
            return self.value, self.REG_SZ

    reg = Registry()
    assert not is_enabled(reg)
    set_enabled(True, reg)
    assert is_enabled(reg)
    assert "--background" in reg.value
    set_enabled(False, reg)
    set_enabled(False, reg)
    assert not is_enabled(reg)


def test_psutil_actual_process_scan():
    me = psutil.Process()
    value = Settings(monitor=True, games=[me.exe()])
    assert any(e["pid"] == me.pid for e in ProcessMonitor().scan(value))


@pytest.mark.parametrize("reason", ["critical", "owner", "session", "query", "access"])
def test_native_termination_fail_closed(reason, monkeypatch, tmp_path):
    import ctypes as c
    from ctypes import wintypes as w

    from jack_guard.security import windows

    path = str(tmp_path / "game.exe")
    terminate = Mock()
    close = Mock()

    def image(handle, flags, buffer, size):
        buffer.value = path
        return reason != "query"

    def critical(handle, pointer):
        c.cast(pointer, c.POINTER(w.BOOL)).contents.value = reason == "critical"
        return True

    kernel = SimpleNamespace(
        OpenProcess=lambda *a: 0 if reason == "access" else 100,
        CloseHandle=close,
        GetCurrentProcess=lambda: 101,
        QueryFullProcessImageNameW=image,
        IsProcessCritical=critical,
        TerminateProcess=terminate,
    )
    adv = SimpleNamespace(EqualSid=lambda *a: reason != "owner")
    monkeypatch.setattr(windows, "libraries", lambda: (kernel, adv))
    monkeypatch.setattr(windows, "open_token", lambda a, p: p + 100)

    def info(adv, token, kind):
        if kind == 1:
            return c.pointer(windows.TOKEN_USER(1, 0))
        return SimpleNamespace(raw=b"other" if reason == "session" and token == 200 else b"same")

    monkeypatch.setattr(windows, "token_info", info)
    with pytest.raises(PermissionError):
        windows.terminate_owned(12345, path)
    terminate.assert_not_called()
    if reason != "access":
        assert close.call_count >= 1
