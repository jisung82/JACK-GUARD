import os
import time
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from jack_guard.app import Controller
from jack_guard.config.store import Store, validate
from jack_guard.core.hotkeys import Hotkeys
from jack_guard.security.passwords import hash_password
from jack_guard.ui.main_window import MainWindow
from jack_guard.ui.swarm import SwarmOverlay
from jack_guard.ui.terminal import COMMANDS, CommandLine


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def controller(app, tmp_path, monkeypatch):
    monkeypatch.setattr("jack_guard.app.Hotkeys", lambda callbacks: Hotkeys(callbacks, Mock()))
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: True)
    monkeypatch.setattr("jack_guard.core.startup.is_enabled", lambda: False)
    monkeypatch.setattr("jack_guard.core.startup.set_enabled", lambda value: None)
    value = Controller(app, Store(tmp_path))
    value.window.show()
    yield value
    value.cleanup()
    value.window.controller = None
    value.window.close()


def test_command_completion_and_history(app):
    line = CommandLine()
    line.show()
    line.setFocus()
    received = []
    line.submitted.connect(received.append)
    line.setText("privacy ")
    QTest.keyClick(line, Qt.Key.Key_Tab)
    assert line.text() == "privacy on"
    QTest.keyClick(line, Qt.Key.Key_Tab)
    assert line.text() == "privacy off"
    QTest.keyClick(line, Qt.Key.Key_Return)
    assert received == ["privacy off"]
    line.setText("status")
    line.submit()
    line.setText("draft")
    QTest.keyClick(line, Qt.Key.Key_Up)
    assert line.text() == "status"
    QTest.keyClick(line, Qt.Key.Key_Up)
    assert line.text() == "privacy off"
    QTest.keyClick(line, Qt.Key.Key_Down)
    QTest.keyClick(line, Qt.Key.Key_Down)
    assert line.text() == "draft"
    QTest.keyClick(line, Qt.Key.Key_Escape)
    assert line.text() == ""
    QTest.keyClicks(line, "status")
    QTest.qWait(20)
    QTest.keyClick(line, Qt.Key.Key_Return)
    assert received[-1] == "status"
    assert not line.completer().popup().isVisible()
    line.close()


def test_real_status_and_command_buttons_share_lock_backend(controller, monkeypatch):
    lock = Mock()
    monkeypatch.setattr("jack_guard.app.lock_workstation", lock)
    controller.execute_command("lock")
    QTest.mouseClick(
        controller.window.lock_button,
        Qt.MouseButton.LeftButton,
        pos=controller.window.lock_button.rect().center(),
    )
    controller.window.intro.start(3, 5, False)
    QTest.mouseClick(
        controller.window.intro.lock_button,
        Qt.MouseButton.LeftButton,
        pos=controller.window.intro.lock_button.rect().center(),
    )
    assert lock.call_count == 3
    assert not controller.window.intro.active
    controller.execute_command("status")
    assert "STOPPED" in controller.window.console.toPlainText()
    assert "READY" in controller.window.console.toPlainText()


@pytest.mark.parametrize(
    "command",
    [
        "powershell Get-Process",
        "cmd /c whoami",
        "lock; exit",
        "$(calc)",
        "process list & calc",
        "__import__('os')",
    ],
)
def test_commands_reject_shell_and_code(controller, command, monkeypatch):
    shell = Mock(side_effect=AssertionError("Shell must never execute"))
    monkeypatch.setattr("subprocess.run", shell)
    assert controller.execute_command(command) is False
    shell.assert_not_called()
    assert "Unknown command" in controller.window.console.toPlainText()


def test_monitor_gui_command_agreement_and_password_gate(controller, monkeypatch):
    controller.execute_command("monitor on")
    assert controller.settings.monitor
    assert controller.window.states["MONITOR"].text() == "RUNNING"
    controller.scan_failed()
    assert controller.window.states["MONITOR"].text() == "ERROR"
    controller.scan_done([])
    assert controller.window.states["MONITOR"].text() == "RUNNING"
    controller.window.pause_button.click()
    assert not controller.settings.monitor
    monkeypatch.setattr(controller, "authorized", lambda: False)
    controller.execute_command("monitor on")
    assert not controller.settings.monitor
    controller.execute_command("logs clear")
    assert controller.events.read()
    monkeypatch.setattr(controller, "authorized", lambda: True)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    controller.execute_command("logs clear")
    assert controller.events.read() == ""


def test_privacy_commands_are_idempotent(controller):
    controller.execute_command("privacy on")
    controller.execute_command("privacy on")
    assert controller.privacy.active
    assert controller.window.states["PRIVACY"].text() == "ENABLED"
    controller.execute_command("privacy off")
    assert not controller.privacy.active
    assert controller.window.states["PRIVACY"].text() == "DISABLED"
    assert controller.window.isVisible()


def test_read_commands_and_async_process_list(controller):
    for command in ("help", "version", "monitor status", "logs"):
        assert controller.execute_command(command)
    assert all(command in COMMANDS for command in ("clear", "exit", "settings"))
    controller.execute_command("process list")
    for _ in range(100):
        QApplication.processEvents()
        if not controller.list_busy:
            break
        QTest.qWait(20)
    assert not controller.list_busy
    assert "CURRENT USER" in controller.window.console.toPlainText()
    controller.execute_command("clear")
    assert controller.window.console.toPlainText() == ""


def test_intro_first_launch_policy_replay_and_motion_preferences(controller, monkeypatch):
    monkeypatch.setattr("jack_guard.app.system_reduced_motion", lambda: True)
    assert not controller.start_intro(True)
    monkeypatch.setattr("jack_guard.app.system_reduced_motion", lambda: False)
    assert controller.start_intro()
    assert controller.settings.intro_seen
    controller.window.intro.finish("test")
    assert not controller.start_intro()
    assert controller.start_intro(replay=True)
    controller.window.intro.finish("test")
    controller.settings.swarm_enabled = False
    assert not controller.start_intro(replay=True)


@pytest.mark.parametrize(
    "change",
    [{"swarm_speed": 0}, {"swarm_speed": True}, {"swarm_cursors": 4}, {"swarm_enabled": "yes"}],
)
def test_invalid_motion_preferences(change):
    with pytest.raises(ValueError):
        validate(change)


def test_legacy_settings_gain_motion_defaults_without_losing_password():
    password = hash_password("legacy settings password")
    loaded = validate({"password": password, "monitor": False})
    assert loaded.password == password
    assert loaded.swarm_enabled and not loaded.intro_seen
    assert loaded.swarm_cursors == 5 and loaded.swarm_speed == 1


def test_swarm_play_skip_resize_and_idle_timer(app):
    window = MainWindow()
    window.show()
    app.processEvents()
    overlay = SwarmOverlay(window)
    window.intro = overlay
    reports = []
    overlay.completed.connect(reports.append)
    overlay.start(3, 8, False)
    QTest.qWait(120)
    assert overlay.active and overlay.snapshot and len(overlay.regions) == 6
    window.resize(900, 600)
    QTest.qWait(50)
    assert overlay.size() == window.center.size()
    QTest.keyClick(overlay, Qt.Key.Key_Escape)
    assert not overlay.active and not overlay.timer.isActive()
    assert reports[-1]["reason"] == "keyboard-skip"
    overlay.start(3, 3, False)
    QTest.qWait(1100)
    assert reports[-1]["reason"] == "complete"
    assert reports[-1]["paints"] > 1
    assert not overlay.timer.isActive() and overlay.snapshot is None
    window.close()


def test_swarm_reduces_motion_when_frames_are_slow(app):
    window = MainWindow()
    window.show()
    overlay = SwarmOverlay(window)
    reports = []
    overlay.completed.connect(reports.append)
    overlay.start(1, 5, True)
    overlay.intervals = [60.0] * 7
    overlay.previous = time.perf_counter() - 0.06
    overlay.tick()
    assert reports[-1]["reason"] == "reduced-frame-rate"
    assert not overlay.timer.isActive()
    window.close()
