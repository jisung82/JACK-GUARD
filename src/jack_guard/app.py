import argparse
import json
import os
import sys
import time
import traceback
from copy import deepcopy
from pathlib import Path

import psutil
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

from jack_guard import __version__
from jack_guard.config.store import Settings, Store
from jack_guard.core import startup
from jack_guard.core.hotkeys import Hotkeys
from jack_guard.core.privacy import Privacy
from jack_guard.core.process_monitor import ProcessMonitor
from jack_guard.core.windows_lock import lock_workstation
from jack_guard.logging.events import Events
from jack_guard.security.passwords import verify_password
from jack_guard.ui.colors import COLOR_HELP, color_stylesheet, parse_color
from jack_guard.ui.design import STYLE, terminal_font
from jack_guard.ui.main_window import MainWindow
from jack_guard.ui.settings import SettingsDialog
from jack_guard.ui.swarm import SwarmOverlay, system_reduced_motion
from jack_guard.ui.terminal import COMMANDS, HELP


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


class ProcessList(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = ScanSignals()

    def run(self):
        try:
            owner = psutil.Process().username()
            result = []
            for process in psutil.process_iter(["pid", "name", "username"]):
                try:
                    if process.info["username"] == owner:
                        result.append((process.info["pid"], process.info["name"] or "?"))
                except psutil.Error:
                    continue
            self.signals.done.emit(sorted(result)[:512])
        except Exception:
            self.signals.failed.emit()


def app_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("#090B0D"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("#E6E8EA"))
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
        self.monitor_error = False
        self.list_busy = False
        self.process_pool = QThreadPool()
        self.process_pool.setMaxThreadCount(1)
        self.animation_report = {}
        self.color_code = None
        self.last_color_errorlevel = 0
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
        self.window.command_requested.connect(self.execute_command)
        self.window.replay_requested.connect(self.replay_intro)
        self.window.pause_button.clicked.connect(self.pause)
        self.window.intro = SwarmOverlay(self.window)
        self.window.intro.completed.connect(self.intro_completed)
        self.window.intro.emergency_lock.connect(self.lock)
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)
        self.timer.start(2000)
        self.event("프로그램 시작")
        if self.hotkey_error:
            self.event("단축키 오류", self.hotkey_error)
        self.window.write(
            f"JACK GUARD {__version__} / TERMINAL EDITION\n"
            "Local commands ready. Type help to begin.\n"
            "Windows 잠금만 실제 OS 접근을 차단합니다.\n"
        )
        self.window.command.setFocus()
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
        values = {
            "SESSION": ("ACTIVE / 현재 사용자", "#E6E8EA"),
            "PRIVACY": ("ENABLED" if self.privacy.active else "DISABLED", "#E6E8EA"),
            "MONITOR": (
                "ERROR"
                if self.monitor_error
                else "RUNNING"
                if self.settings.monitor
                else "STOPPED",
                "#E77B7B"
                if self.monitor_error
                else "#9BCB87"
                if self.settings.monitor
                else "#89939B",
            ),
            "HOTKEY": (
                "ERROR" if self.hotkey_error else "READY",
                "#E8BD73" if self.hotkey_error else "#9BCB87",
            ),
        }
        for key, (text, color) in values.items():
            self.window.states[key].setText(text)
            if self.window.terminal_colors:
                color = self.window.terminal_colors[1]
            self.window.states[key].setStyleSheet(f"color:{color}")
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
        if self.window.intro:
            self.window.intro.finish("lock-request")
        self.event("잠금 요청")
        try:
            lock_workstation()
            return True
        except OSError:
            self.event("잠금 오류")
            QMessageBox.warning(
                self.window, "잠금 실패", "Windows가 잠금 요청을 수락하지 않았습니다."
            )
            return False

    def toggle_privacy(self):
        if self.privacy.active:
            self.privacy_off()
        else:
            self.privacy_on()

    def privacy_on(self):
        if self.privacy.active:
            return True
        if not QSystemTrayIcon.isSystemTrayAvailable() and not self.settings.overlay:
            QMessageBox.warning(
                self.window, "트레이 없음", "창 복원을 위해 화면 가림 옵션을 사용하세요."
            )
            return False
        self.window.intro.finish("privacy")
        self.privacy.enter(self.settings.overlay)
        self.refresh()
        return True

    def privacy_off(self):
        self.privacy.leave()
        self.refresh()
        return True

    def tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.privacy_off()

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
        self.window.intro.finish("settings")
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
        return self.set_monitor(not self.settings.monitor)

    def set_monitor(self, enabled):
        if self.settings.monitor == enabled:
            return True
        if self.authorized():
            value = deepcopy(self.settings)
            value.monitor = enabled
            try:
                self.apply_settings(value, startup.is_enabled())
                return True
            except (OSError, ValueError) as error:
                QMessageBox.warning(self.window, "설정 실패", str(error))
        return False

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
        self.monitor_error = False
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
        self.monitor_error = False
        self.refresh()
        for item in events:
            detail = f"{item['name']} (PID {item['pid']}) · {item['action']}"
            self.event("게임 프로세스", detail)
            if self.settings.notifications and not self.quitting:
                self.tray.showMessage("게임 실행 감지", detail)

    def scan_failed(self):
        self.busy = False
        self.monitor_error = True
        self.event("프로세스 검사 오류")

    def execute_command(self, raw):
        if self.window.intro.active:
            self.window.intro.finish("command")
        command = " ".join(str(raw).strip().lower().split())
        self.window.write(f"jack@guard > {raw}")
        if command == "color" or command.startswith("color "):
            return self.color_command(command.split()[1:])
        if command not in COMMANDS:
            self.window.write("ERROR  Unknown command. Type help.\n")
            return False
        if command == "help":
            self.window.write(HELP)
        elif command == "status":
            self.window.write(
                "\n".join(f"{key:<10} {label.text()}" for key, label in self.window.states.items())
            )
        elif command == "lock":
            self.window.write(
                "OK  Windows 잠금 요청 수락." if self.lock() else "ERROR  Windows 잠금 요청 실패."
            )
        elif command.startswith("privacy "):
            success = self.privacy_on() if command.endswith("on") else self.privacy_off()
            self.window.write(
                ("OK  " if success else "ERROR  ")
                + (
                    "프라이버시 활성. OS 잠금 아님."
                    if self.privacy.active
                    else "프라이버시 비활성."
                )
            )
        elif command == "monitor status":
            self.window.write(
                f"MONITOR  {self.window.states['MONITOR'].text()}\n"
                f"WATCHED  {len(self.settings.games)}  /  "
                f"EXCEPTIONS  {len(self.settings.exceptions)}\n"
                f"ACTION   {'종료 동의됨' if self.settings.terminate else '알림만'}"
            )
        elif command in ("monitor on", "monitor off"):
            success = self.set_monitor(command.endswith("on"))
            self.window.write("OK  감지 설정 적용." if success else "CANCEL  설정 변경 취소.")
        elif command == "process list":
            self.list_processes()
        elif command == "logs":
            self.show_logs()
        elif command == "logs clear":
            self.clear_logs()
        elif command == "settings":
            self.open_settings()
        elif command == "version":
            self.window.write(f"JACK GUARD {__version__} / TERMINAL EDITION")
        elif command == "clear":
            self.window.console.clear()
        elif command == "exit":
            self.quit()
        return True

    def color_command(self, arguments):
        if arguments == ["/?"]:
            self.window.write(COLOR_HELP)
            self.last_color_errorlevel = 0
            return True
        try:
            if len(arguments) > 1:
                raise ValueError("COLOR: 색 코드는 공백 없이 지정하세요. color /?")
            if not arguments:
                self.window.terminal_colors = None
                self.color_code = None
                self.window.setStyleSheet("")
            else:
                code, colors = parse_color(arguments[0])
                self.window.setStyleSheet(color_stylesheet(*colors))
                self.window.terminal_colors = colors
                self.color_code = code
            self.last_color_errorlevel = 0
            self.refresh()
            self.window.write(
                f"OK  COLOR {self.color_code}" if self.color_code else "OK  기본 색상 복원."
            )
            return True
        except ValueError as error:
            self.last_color_errorlevel = 1
            self.window.write(f"ERRORLEVEL 1  {error}")
            return False

    def show_logs(self):
        try:
            lines = self.events.read().splitlines()[:100]
            formatted = []
            for line in lines:
                try:
                    item = json.loads(line)
                    formatted.append(f"{item['time'][:19]}  {item['event']}  {item['detail']}")
                except (ValueError, KeyError, TypeError):
                    continue
            self.window.write("\n".join(formatted) or "EMPTY  로컬 이벤트 없음.")
        except OSError:
            self.window.write("ERROR  로그를 읽을 수 없습니다.")

    def clear_logs(self):
        if not self.authorized():
            self.window.write("CANCEL  로그 삭제 취소.")
            return False
        if QMessageBox.question(self.window, "로그 삭제", "모든 로컬 로그를 삭제할까요?") != (
            QMessageBox.StandardButton.Yes
        ):
            self.window.write("CANCEL  로그 삭제 취소.")
            return False
        try:
            self.events.clear()
            self.refresh()
            self.window.write("OK  로컬 로그 삭제 완료.")
            return True
        except OSError:
            self.window.write("ERROR  로그를 삭제할 수 없습니다.")
            return False

    def list_processes(self):
        if self.list_busy:
            self.window.write("BUSY  프로세스 조회 중.")
            return
        self.list_busy = True
        self.window.write("QUERY  현재 사용자 프로세스 조회 중…")
        self.list_task = ProcessList()
        self.list_task.signals.done.connect(self.processes_ready)
        self.list_task.signals.failed.connect(self.processes_failed)
        self.process_pool.start(self.list_task)

    def processes_ready(self, rows):
        self.list_busy = False
        if not self.quitting:
            self.window.write(
                "PID       PROCESS / CURRENT USER\n"
                + "\n".join(f"{pid:<9} {name}" for pid, name in rows)
                + f"\nOK  {len(rows)} processes (maximum 512)."
            )

    def processes_failed(self):
        self.list_busy = False
        self.window.write("ERROR  프로세스 조회 실패.")

    def replay_intro(self):
        return self.start_intro(replay=True)

    def start_intro(self, replay=False):
        if not self.settings.swarm_enabled:
            self.window.write("INTRO  Disabled in settings.")
            return False
        if system_reduced_motion():
            if replay:
                self.window.write("INTRO  Skipped: Windows reduced motion policy.")
            return False
        if not replay and self.settings.intro_seen and not self.settings.swarm_every_launch:
            return False
        self.window.intro.start(
            self.settings.swarm_speed, self.settings.swarm_cursors, self.settings.reduce_motion
        )
        if not self.settings.intro_seen:
            self.settings.intro_seen = True
            try:
                self.store.save(self.settings)
            except (OSError, ValueError):
                self.event("인트로 설정 저장 오류")
        return True

    def intro_completed(self, report):
        self.animation_report = report

    def quit(self):
        self.app.quit()

    def cleanup(self):
        if self.quitting:
            return
        self.quitting = True
        self.timer.stop()
        self.window.intro.finish("shutdown")
        self.pool.waitForDone()
        self.process_pool.waitForDone()
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
    app.setFont(terminal_font())
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
        if not args.smoke_test:
            QTimer.singleShot(0, controller.start_intro)
    if args.smoke_test:
        # Exercise GUI lifecycle without locking Windows, starting games or changing startup.
        def smoke():
            try:
                controller.window.show()
                app.processEvents()
                controller.execute_command("status")
                controller.execute_command("version")
                assert "TERMINAL EDITION" in controller.window.console.toPlainText()
                assert controller.execute_command("color 0a")
                assert controller.color_code == "0A"
                assert not controller.execute_command("color aa")
                assert controller.color_code == "0A" and controller.last_color_errorlevel == 1
                assert controller.execute_command("color a")
                assert controller.execute_command("color f0")
                assert controller.execute_command("color /?")
                assert controller.execute_command("color")
                assert controller.window.terminal_colors is None
                if args.screenshot:
                    controller.window.grab().save(str(args.screenshot))
                controller.execute_command("color 1f")
                controller.window.intro.start(3, 5, False)
                QTimer.singleShot(1100, smoke_animation)
            except Exception:
                app.exit(4)

        def smoke_animation():
            try:
                assert not controller.window.intro.active
                assert controller.animation_report["reason"] == "complete"
                controller.execute_command("color")
                controller.window.intro.start(1, 8, False)
                controller.window.resize(900, 600)
                QTimer.singleShot(80, smoke_finish)
            except Exception:
                app.exit(4)

        def smoke_finish():
            try:
                assert controller.window.intro.size() == controller.window.center.size()
                controller.window.intro.finish("smoke-skip")
                assert not controller.window.intro.timer.isActive()
                controller.privacy.enter(True)
                assert controller.privacy.active and controller.privacy.covers
                controller.privacy.leave()
                assert controller.window.isVisible() and not controller.privacy.active
                assert controller.hotkeys.registered or controller.hotkey_error
                (directory / "smoke-result.json").write_text(
                    json.dumps(
                        {
                            "gui": "PASS",
                            "commands": "PASS",
                            "color": "PASS",
                            "intro": "PASS",
                            "intro_resize_skip": "PASS",
                            "overlay_restore": "PASS",
                            "hotkeys": "PASS" if not controller.hotkey_error else "FAIL",
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
