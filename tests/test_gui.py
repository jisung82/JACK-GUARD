import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from jack_guard.app import Controller
from jack_guard.config.store import Store
from jack_guard.core.hotkeys import Hotkeys
from jack_guard.core.privacy import Privacy
from jack_guard.ui.main_window import MainWindow
from jack_guard.ui.settings import SettingsDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_privacy_all_screens_restore(app):
    events = []
    window = MainWindow()
    window.show()
    privacy = Privacy(window, lambda *event: events.append(event))
    privacy.enter(True)
    assert not window.isVisible()
    assert len(privacy.covers) == len(app.screens())
    privacy.leave()
    assert window.isVisible() and not privacy.covers
    assert len(events) == 2
    window.close()


def test_controller_lifecycle_settings_and_tray(app, tmp_path, monkeypatch):
    # Native registration is tested by the package smoke; lifecycle tests are isolated
    # from shortcuts owned by other applications on the developer's desktop.
    monkeypatch.setattr("jack_guard.app.Hotkeys", lambda callbacks: Hotkeys(callbacks, Mock()))
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: True)
    monkeypatch.setattr("jack_guard.core.startup.is_enabled", lambda: False)
    monkeypatch.setattr("jack_guard.core.startup.set_enabled", lambda v: None)
    controller = Controller(app, Store(tmp_path))
    try:
        controller.window.show()
        dialog = SettingsDialog(controller)
        assert dialog.tabs.count() == 6
        assert not dialog.collect().terminate
        dialog.close()
        controller.window.close()
        assert not controller.window.isVisible()
        controller.tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
        assert controller.window.isVisible()
        assert "중지" in controller.window.status.text()
        controller.apply_settings(controller.settings, False)
        assert controller.store.path.exists()
        controller.cleanup()
        assert not controller.hotkeys.registered
        assert not controller.tray.isVisible()
        assert "프로그램 종료" in controller.events.read()
    finally:
        controller.cleanup()
        controller.window.close()


def test_single_instance_lock_and_release(tmp_path, app):
    path = str(tmp_path / "instance.lock")
    first, second = QLockFile(path), QLockFile(path)
    assert first.tryLock(0)
    assert not second.tryLock(0)
    first.unlock()
    assert second.tryLock(0)
    second.unlock()
