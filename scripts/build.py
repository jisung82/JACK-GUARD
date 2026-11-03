"""Build both portable layouts, include license texts, and generate SHA256 sums."""

import importlib.metadata
import os
import shutil
import subprocess
import sys
from pathlib import Path

from package import package_outputs

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows build host required")
    licenses = ROOT / "build" / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    for package in ("PySide6-Essentials", "shiboken6", "psutil", "pyinstaller"):
        dist = importlib.metadata.distribution(package)
        for entry in dist.files or []:
            if ("license" in str(entry).lower() or "copying" in str(entry).lower()) and (
                ".dist-info/" in str(entry).replace("\\", "/")
            ):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    shutil.copy2(source, licenses / f"{package}-{source.name}")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
    shutil.copytree(ROOT / "docs" / "licenses", licenses, dirs_exist_ok=True)
    required = ["LGPL-3.0.txt", "GPL-3.0.txt"]
    if any(not (licenses / filename).exists() for filename in required):
        raise SystemExit("Missing Qt license texts in docs/licenses")
    common = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
    ]
    environment = os.environ.copy()
    windows = Path(os.environ["SystemRoot"])
    # External image/PDF tools on PATH can carry an incompatible, unversioned ICU DLL.
    environment["PATH"] = os.pathsep.join(
        map(
            str,
            [
                Path(sys.executable).parent,
                Path(sys.base_prefix),
                windows / "System32",
                windows,
                windows / "System32" / "Wbem",
            ],
        )
    )
    environment["JACK_GUARD_ONEFILE"] = "0"
    subprocess.run(
        [
            *common,
            "--distpath",
            str(ROOT / "dist" / "portable"),
            str(ROOT / "scripts" / "jack_guard.spec"),
        ],
        cwd=ROOT,
        check=True,
        env=environment,
    )
    folder = ROOT / "dist" / "portable" / "JACK-GUARD"
    for filename in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / filename, folder / filename)
    shutil.copytree(licenses, folder / "licenses", dirs_exist_ok=True)
    shutil.make_archive(
        str(ROOT / "dist" / "JACK-GUARD-portable"), "zip", ROOT / "dist" / "portable", "JACK-GUARD"
    )
    environment["JACK_GUARD_ONEFILE"] = "1"
    subprocess.run(
        [
            *common,
            "--distpath",
            str(ROOT / "dist"),
            str(ROOT / "scripts" / "jack_guard.spec"),
        ],
        cwd=ROOT,
        check=True,
        env=environment,
    )
    package_outputs()


if __name__ == "__main__":
    main()
