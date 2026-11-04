"""Capture the real Qt interface and measure the engine; run once per QT_SCALE_FACTOR."""

import argparse
import json
import os
import time
from pathlib import Path

import psutil
from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontInfo
from PySide6.QtWidgets import QApplication

from jack_guard.app import Controller
from jack_guard.config.store import Settings, Store
from jack_guard.ui.design import STYLE, terminal_font
from jack_guard.ui.settings import SettingsDialog
from jack_guard.ui.swarm import system_reduced_motion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--gif", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setFont(terminal_font())
    app.setStyleSheet(STYLE)
    store = Store(args.data_dir)
    store.save(Settings(lock_hotkey="Ctrl+Alt+Shift+F23", privacy_hotkey="Ctrl+Alt+Shift+F24"))
    c = Controller(app, store)
    c.window.show()
    process = psutil.Process()
    report = {
        "scale": os.environ.get("QT_SCALE_FACTOR", "1"),
        "font": QFontInfo(app.font()).family(),
        "screens": len(app.screens()),
        "os_reduced_motion": system_reduced_motion(),
        "runs": [],
    }
    c.window.intro.completed.connect(lambda item: report["runs"].append(dict(item)))
    frames = []
    capture = QTimer()
    capture.setInterval(40)

    def capture_frame():
        pixmap = c.window.grab()
        picture = pixmap.toImage().convertToFormat(pixmap.toImage().Format.Format_RGBA8888)
        frames.append(
            Image.frombytes(
                "RGBA", (picture.width(), picture.height()), bytes(picture.bits())
            ).convert("RGB")
        )

    capture.timeout.connect(capture_frame)

    def benchmark():
        report["rss_before_mib"] = round(process.memory_info().rss / 1024**2, 2)
        # Explicit engine test: record OS policy separately; production always honors it.
        c.window.intro.start(1, 5, False)
        QTimer.singleShot(3200, second_run)

    def second_run():
        c.window.intro.start(3, 8, True)
        QTimer.singleShot(1200, idle_start)

    def idle_start():
        report["rss_after_mib"] = round(process.memory_info().rss / 1024**2, 2)
        report["idle_timer_active"] = c.window.intro.timer.isActive()
        report["idle_cpu_start"] = sum(process.cpu_times()[:2])
        report["idle_time_start"] = time.perf_counter()
        QTimer.singleShot(1200, screenshots)

    def screenshots():
        duration = time.perf_counter() - report.pop("idle_time_start")
        delta = sum(process.cpu_times()[:2]) - report.pop("idle_cpu_start")
        report["idle_cpu_percent_one_core"] = round(100 * delta / duration, 2)
        report["device_pixel_ratio"] = c.window.devicePixelRatioF()
        c.execute_command("status")
        c.execute_command("monitor status")
        c.window.command.setFocus()
        c.window.grab().save(str(args.output / "terminal.png"))
        c.window.resize(850, 550)
        QTimer.singleShot(100, minimum)

    def minimum():
        c.window.grab().save(str(args.output / "minimum.png"))
        report["minimum_size"] = [c.window.width(), c.window.height()]
        report["console_viewport"] = [
            c.window.console.viewport().width(),
            c.window.console.viewport().height(),
        ]
        c.window.resize(1100, 700)
        dialog = SettingsDialog(c)
        dialog.show()
        c.qa_dialog = dialog
        QTimer.singleShot(100, settings)

    def settings():
        c.qa_dialog.tabs.setCurrentIndex(5)
        c.qa_dialog.grab().save(str(args.output / "animation-settings.png"))
        c.qa_dialog.close()
        if args.gif:
            c.window.console.clear()
            c.window.write("JACK GUARD / TERMINAL EDITION\nType help to begin.\n")
            c.window.intro.start(1, 5, False)
            capture.start()
            QTimer.singleShot(3000, finish)
        else:
            finish()

    def finish():
        capture.stop()
        if frames:
            frames[0].save(
                args.output / "swarm-intro.gif",
                save_all=True,
                append_images=frames[1:],
                duration=40,
                loop=0,
                optimize=True,
            )
        report["capture_frames"] = len(frames)
        (args.output / "performance.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        c.cleanup()
        app.quit()

    QTimer.singleShot(150, benchmark)
    app.exec()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
