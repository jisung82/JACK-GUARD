import subprocess
import sys

VALUE = "JACK GUARD"
KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def command():
    args = [sys.executable]
    if not getattr(sys, "frozen", False):
        args += ["-m", "jack_guard"]
    return subprocess.list2cmdline([*args, "--background"])


def set_enabled(enabled: bool, registry=None):
    if registry is None:
        import winreg as registry
    with registry.CreateKey(registry.HKEY_CURRENT_USER, KEY) as key:
        if enabled:
            registry.SetValueEx(key, VALUE, 0, registry.REG_SZ, command())
        else:
            try:
                registry.DeleteValue(key, VALUE)
            except FileNotFoundError:
                pass


def is_enabled(registry=None):
    if registry is None:
        import winreg as registry
    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, KEY) as key:
            value, _ = registry.QueryValueEx(key, VALUE)
            return value == command()
    except FileNotFoundError:
        return False
