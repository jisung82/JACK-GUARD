"""Capture actual COLOR results using an isolated controller; never invoke a shell."""

import argparse
import json
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from jack_guard.app import Controller
from jack_guard.config.store import Settings, Store
from jack_guard.ui.design import STYLE, terminal_font


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setFont(terminal_font())
    app.setStyleSheet(STYLE)
    store = Store(args.data_dir)
    store.save(Settings(lock_hotkey="Ctrl+Alt+Shift+F23", privacy_hotkey="Ctrl+Alt+Shift+F24"))
    c = Controller(app, store)
    c.window.show()
    captures = iter(["0A", "1F", "F0", "default"])
    results = []

    def next_color():
        code = next(captures, None)
        if code is None:
            (args.output / "results.json").write_text(
                json.dumps(results, indent=2), encoding="utf-8"
            )
            c.cleanup()
            app.quit()
            return
        c.execute_command("clear")
        assert c.execute_command("color" if code == "default" else f"color {code}")
        c.execute_command("status")
        app.processEvents()
        assert c.window.grab().save(str(args.output / f"color-{code}.png"))
        results.append(
            {
                "code": code,
                "active": c.color_code,
                "colors": c.window.terminal_colors,
                "result": "PASS",
            }
        )
        QTimer.singleShot(100, next_color)

    QTimer.singleShot(100, next_color)
    app.exec()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
