"""Launch a bundled binary with isolated settings; timeout and exit are release gates."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    exe = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="jack-guard-smoke-") as temp:
        environment = os.environ.copy()
        environment["LOCALAPPDATA"] = temp
        data = Path(temp) / "settings"
        data.mkdir()
        (data / "settings.json").write_text(
            json.dumps(
                {
                    "lock_hotkey": "Ctrl+Alt+Shift+F23",
                    "privacy_hotkey": "Ctrl+Alt+Shift+F24",
                }
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [str(exe), "--smoke-test", "--data-dir", str(data)],
            env=environment,
            timeout=90,
            check=True,
        )
        report = json.loads((data / "smoke-result.json").read_text(encoding="utf-8"))
        assert result.returncode == 0 and report["gui"] == "PASS"
        assert report["overlay_restore"] == "PASS"
        assert report["commands"] == "PASS"
        assert report["color"] == "PASS"
        assert report["intro"] == "PASS" and report["intro_resize_skip"] == "PASS"
        assert report["hotkeys"] == "PASS", "Test hotkeys could not be registered"
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
