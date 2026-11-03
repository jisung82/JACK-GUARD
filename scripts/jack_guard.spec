# Do not shadow Windows 10/11 API sets and ICU with build-host DLL copies.
import os
from pathlib import Path

root = Path(SPECPATH).parent
onefile = os.environ.get("JACK_GUARD_ONEFILE") == "1"
a = Analysis(
    [str(root / "scripts" / "entry.py")], pathex=[str(root / "src")], binaries=[],
    datas=[(str(root / "build" / "licenses"), "licenses"),
           (str(root / "THIRD_PARTY_NOTICES.md"), "."), (str(root / "LICENSE"), ".")],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["PySide6.QtQml", "PySide6.QtNetwork"], noarchive=False,
)


def os_component(entry):
    name, source, _ = entry
    base = Path(name).name.lower()
    if base.startswith("api-ms-win-"):
        return True
    return base in {"icuuc.dll", "ucrtbase.dll"} or base.startswith("icudt")


a.binaries = [entry for entry in a.binaries if not os_component(entry)]
pyz = PYZ(a.pure)
if onefile:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="JACK-GUARD", debug=False,
              bootloader_ignore_signals=False, strip=False, upx=False, console=False)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="JACK-GUARD", debug=False,
              bootloader_ignore_signals=False, strip=False, upx=False, console=False)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="JACK-GUARD")
