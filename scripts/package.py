"""Refresh portable documents, ZIP and checksums without recompiling binaries."""

import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package_outputs():
    folder = ROOT / "dist" / "portable" / "JACK-GUARD"
    for name in ("README.md", "LICENSE", "SECURITY.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, folder / name)
    shutil.copytree(
        ROOT / "docs",
        folder / "docs",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("licenses"),
    )
    pictures = ROOT / "assets" / "screenshots" / "100"
    if pictures.exists():
        shutil.copytree(pictures, folder / "assets" / "screenshots" / "100", dirs_exist_ok=True)
    shutil.make_archive(
        str(ROOT / "dist" / "JACK-GUARD-portable"), "zip", ROOT / "dist" / "portable", "JACK-GUARD"
    )
    lines = []
    for name in ("JACK-GUARD.exe", "JACK-GUARD-portable.zip"):
        with (ROOT / "dist" / name).open("rb") as stream:
            lines.append(f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {name}")
    (ROOT / "dist" / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    package_outputs()
