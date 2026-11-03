import argparse
import json
import os
import sys
import time
import traceback
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import (
    QLockFile,
    QObject,
    QRunnable,
    QStandardPaths,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from jack_guard.config.store import Settings, Store
from jack_guard.core import startup
from jack_guard.core.hotkeys import Hotkeys
from jack_guard.core.privacy import Privacy
from jack_guard.core.process_monitor import ProcessMonitor
from jack_guard.core.windows_lock import lock_workstation
from jack_guard.logging.events import Events
from jack_guard.security.passwords import verify_password
from jack_guard.ui.main_window import STYLE, MainWindow
from jack_guard.ui.settings import SettingsDialog


class ScanSignals(QObject):
    done = Signal(list)
    failed = Signal()


class Scan(QRunnable):
    def __init__(self, monitor, settings):
        super().__init__()
        self.monitor, self.settings = monitor, settings
        self.signals = ScanSignals()

    def run(self):
        try:
            self.signals.done.emit(self.monitor.scan(self.settings))
        except Exception:
            self.signals.failed.emit()


def app_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("#111827"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("#64dfbd"))
    font = painter.font()
    font.setPixelSize(35)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), 0x84, "JG")
    painter.end()
    return QIcon(pixmap)


class Controller:
    def __init__(self, app, store, smoke=False):
        self.app, self.store = app, store
        self.settings = store.load()
        self.events = Events(store.directory, self.settings.retention_days)
        self.window = MainWindow()
        self.window.controller = self
        self.window.setWindowIcon(app_icon())
        self.privacy = Privacy(self.window, self.event)
        self.monitor = ProcessMonitor()
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(1)
        self.busy = False
        self.quitting = False
        self.hotkey_error = ""
        self.failed_auth = 0
        self.auth_after = 0.0
        self.smoke = smoke
        self.hotkeys = Hotkeys([self.lock, self.toggle_privacy])
        app.installNativeEventFilter(self.hotkeys)
        try:
            self.hotkeys.register([self.settings.lock_hotkey, self.settings.privacy_hotkey])
        except OSError as error:
            self.hotkey_error = str(error)
        self.tray = QSystemTrayIcon(app_icon(), self.window)
        menu = QMenu()
        for title, callback in [
            ("열기 / 화면 가림 해제", self.privacy.leave),
            ("Windows 잠금", self.lock),
            ("프라이버시 모드", self.toggle_privacy),
            ("감지 일시 중지 / 재개", self.pause),
            ("설정", self.open_settings),
            ("종료", self.quit),
        ]:
            action = QAction(title, menu)
            action.triggered.connect(callback)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()
        self.window.lock_button.clicked.connect(self.lock)
        self.window.privacy_button.clicked.connect(self.toggle_privacy)
        self.window.settings_button.clicked.connect(self.open_settings)
        self.window.pause_button.clicked.connect(self.pause)
        self.window.quit_button.clicked.connect(self.quit)
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)
        self.timer.start(2000)
        self.event("프로그램 시작")
        if self.hotkey_error:
            self.event("단축키 오류", self.hotkey_error)
        app.aboutToQuit.connect(self.cleanup)

    def event(self, kind, detail=""):
        try:
            self.events.add(kind, detail)
        except OSError:
            self.window.status.setText("로그 기록 실패 · 저장 공간과 권한을 확인하세요.")
            return
        self.refresh()

    def refresh(self):
        mode = "활성" if self.settings.monitor else "중지"
        action = "자동 종료 동의됨" if self.settings.terminate else "알림만"
        self.window.status.setText(f"게임 감지: {mode} · {action} · Windows 잠금: 요청 시 실행")
        self.window.hotkey_label.setText(
            self.hotkey_error
            or f"잠금 {self.settings.lock_hotkey}   |   프라이버시 {self.settings.privacy_hotkey}"
        )
        try:
            recent = []
            for line in self.events.read().splitlines()[:50]:
                try:
                    item = json.loads(line)
                    recent.append(
                        f"{item['time'][:19].replace('T', ' ')}  {item['event']}  {item['detail']}"
                    )
                except (ValueError, KeyError, TypeError):
                    continue
            self.window.recent.setPlainText("\n".join(recent))
        except OSError:
            self.window.recent.setPlainText("로그를 읽을 수 없습니다.")
        self.tray.setToolTip(f"JACK GUARD · 게임 감지 {mode} · {action}")

    def lock(self):
        self.event("잠금 요청")
        try:
            lock_workstation()
        except OSError:
            self.event("잠금 오류")
            QMessageBox.warning(
                self.window, "잠금 실패", "Windows가 잠금 요청을 수락하지 않았습니다."
            )

    def toggle_privacy(self):
        if not QSystemTrayIcon.isSystemTrayAvailable() and not self.settings.overlay:
            QMessageBox.warning(
                self.window, "트레이 없음", "창 복원을 위해 화면 가림 옵션을 사용하세요."
            )
            return
        self.privacy.enter(self.settings.overlay)

    def tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.privacy.leave()

    def authorized(self):
        if not self.settings.password:
            return True
        if time.monotonic() < self.auth_after:
            QMessageBox.warning(self.window, "설정 보호", "잠시 후 다시 시도하세요.")
            return False
        password, ok = QInputDialog.getText(
            self.window, "설정 보호", "설정 비밀번호", QLineEdit.EchoMode.Password
        )
        if not ok:
            return False
        if verify_password(password, self.settings.password):
            self.failed_auth = 0
            return True
        self.failed_auth += 1
        self.auth_after = time.monotonic() + min(60, 2 ** min(self.failed_auth, 6))
        QMessageBox.warning(self.window, "설정 보호", "비밀번호가 일치하지 않습니다.")
        return False

    def open_settings(self):
        self.privacy.leave()
        if self.privacy.dialog:
            self.privacy.dialog.raise_()
            return
        if self.authorized():
            dialog = SettingsDialog(self)
            self.privacy.dialog = dialog
            try:
                dialog.exec()
            finally:
                self.privacy.dialog = None

    def pause(self):
        if self.authorized():
            value = deepcopy(self.settings)
            value.monitor = not value.monitor
            try:
                self.apply_settings(value, startup.is_enabled())
            except (OSError, ValueError) as error:
                QMessageBox.warning(self.window, "설정 실패", str(error))

    def apply_settings(self, value, autostart):
        if self.busy:
            raise ValueError("프로세스 검사 중입니다. 잠시 후 저장하세요.")
        old_start = startup.is_enabled()
        old = self.settings
        try:
            self.hotkeys.register([value.lock_hotkey, value.privacy_hotkey])
            startup.set_enabled(autostart)
            self.store.save(value)
        except (OSError, ValueError):
            try:
                startup.set_enabled(old_start)
                self.hotkeys.register([old.lock_hotkey, old.privacy_hotkey])
            except OSError:
                self.hotkey_error = "설정 복원 실패 · 단축키 및 자동 시작을 확인하세요."
                self.event("설정 복원 오류")
            raise
        self.settings = value
        self.hotkey_error = ""
        self.monitor.seen.clear()
        self.events.retention = value.retention_days
        self.event("설정 변경")

    def poll(self):
        if self.busy or self.quitting or not self.settings.monitor:
            return
        self.busy = True
        self.scan = Scan(self.monitor, deepcopy(self.settings))
        self.scan.signals.done.connect(self.scan_done)
        self.scan.signals.failed.connect(self.scan_failed)
        self.pool.start(self.scan)

    def scan_done(self, events):
        self.busy = False
        for item in events:
            detail = f"{item['name']} (PID {item['pid']}) · {item['action']}"
            self.event("게임 프로세스", detail)
            if self.settings.notifications and not self.quitting:
                self.tray.showMessage("게임 실행 감지", detail)

    def scan_failed(self):
        self.busy = False
        self.event("프로세스 검사 오류")

    def quit(self):
        self.app.quit()

    def cleanup(self):
        if self.quitting:
            return
        self.quitting = True
        self.timer.stop()
        self.pool.waitForDone()
        self.hotkeys.close()
        self.app.removeNativeEventFilter(self.hotkeys)
        for cover in self.privacy.covers:
            cover.close()
        self.tray.hide()
        self.event("프로그램 종료")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--reset-settings", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args(argv)
    app = QApplication([sys.argv[0]])
    app.setApplicationName("JACK GUARD")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLE)
    directory = args.data_dir or Path(
        os.environ.get("LOCALAPPDATA")
        or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    ) / ("JACK-GUARD")
    # Global per-user instance lock, even with alternate data directories.
    lock_dir = Path(os.environ.get("LOCALAPPDATA", str(directory.parent))) / "JACK-GUARD"
    try:
        from jack_guard.config.store import secure_directory

        secure_directory(lock_dir)
        lock = QLockFile(str(lock_dir / "instance.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(100):
            if args.smoke_test:
                return 2
            QMessageBox.information(
                None, "JACK GUARD", "이미 실행 중입니다. 트레이에서 열어주세요."
            )
            return 2
        store = Store(directory)
        if args.reset_settings:
            answer = QMessageBox.question(
                None,
                "설정 초기화",
                "설정·비밀번호·자동 시작을 초기화할까요?\n기존 설정은 삭제되며, 로그는 유지됩니다.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return 0
            startup.set_enabled(False)
            store.save(Settings())
        controller = Controller(app, store, args.smoke_test)
    except (OSError, ValueError):
        if args.smoke_test:
            return 3
        QMessageBox.critical(
            None,
            "JACK GUARD 시작 실패",
            "설정 또는 폴더에 접근할 수 없습니다.\n"
            "손상된 설정은 --reset-settings로 초기화할 수 있습니다.",
        )
        return 1

    def exception_hook(kind, value, tb):
        # Record exception type only: exception messages can contain sensitive user input.
        controller.event("예외", kind.__name__)
        if not getattr(sys, "frozen", False):
            traceback.print_exception(kind, value, tb)
        controller.privacy.leave()
        QMessageBox.warning(
            controller.window, "오류", "작업 중 오류가 발생했습니다. 로그를 확인하세요."
        )

    sys.excepthook = exception_hook
    if not args.background or not QSystemTrayIcon.isSystemTrayAvailable():
        controller.window.show()
    if args.smoke_test:
        # Exercise GUI lifecycle without locking Windows, starting games or changing startup.
        def smoke():
            try:
                controller.window.show()
                app.processEvents()
                if args.screenshot:
                    controller.window.grab().save(str(args.screenshot))
                controller.privacy.enter(True)
                assert controller.privacy.active and controller.privacy.covers
                controller.privacy.leave()
                assert controller.window.isVisible() and not controller.privacy.active
                assert controller.hotkeys.registered or controller.hotkey_error
                (directory / "smoke-result.json").write_text(
                    json.dumps(
                        {
                            "gui": "PASS",
                            "overlay_restore": "PASS",
                            "hotkeys": "PASS" if not controller.hotkey_error else "CONFLICT",
                            "screens": len(app.screens()),
                            "tray_available": QSystemTrayIcon.isSystemTrayAvailable(),
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                app.exit(0)
            except Exception:
                app.exit(4)

        QTimer.singleShot(600, smoke)
    result = app.exec()
    lock.unlock()
    return result
