# Third-party components

The project license is pending owner selection. It does not replace these licenses.

| Component | Version | License / upstream |
| --- | --- | --- |
| CPython | 3.12 | PSF and bundled notices: https://www.python.org/downloads/source/ |
| PySide6 Essentials / Shiboken6 | 6.10.2 | LGPLv3 / GPL / commercial choices: https://code.qt.io/cgit/pyside/pyside-setup.git/ |
| Qt Core, Gui, Widgets and related runtime plugins | 6.10.2 | LGPLv3 and applicable third-party notices: https://code.qt.io/cgit/qt/qtbase.git/ |
| psutil | 7.2.2 | BSD-3-Clause: https://github.com/giampaolo/psutil |
| PyInstaller bootloader | 6.19.0 | GPLv2+ with distribution exception: https://pyinstaller.org/en/stable/license.html |
| Microsoft runtime DLLs | bundled with Python/Qt | Microsoft redistributable runtime terms |

Only Qt Core/Gui/Widgets are directly imported. No GPL-only Qt Addons are used.
The build copies installed distribution license texts and CPython's license into the package,
plus LGPLv3/GPLv3 texts in docs/licenses. PyInstaller uses dynamic Qt libraries.
The exact Qt 6.10.2 qtbase/qtimageformats/qtsvg source notices (210 files) are copied
into docs/licenses/qt with archive SHA256 provenance. A superset of notices is included;
inclusion does not imply every optional Qt source component is shipped.
The portable ZIP exposes DLLs so users can replace/relink compatible Qt/PySide components.
Reverse engineering for debugging changes to LGPL components is permitted to the extent
required by their licenses. No project restriction overrides those rights.
For the one-file build, rebuild from the matching published source with modified libraries
using scripts/build.py; prefer the portable ZIP if direct DLL replacement is needed.

Matching unmodified source is available from the upstream Qt 6.10.2 and PySide 6.10.2 tags:
https://download.qt.io/archive/qt/6.10/6.10.2/submodules/ and
https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.2-src/.
See upstream sources for subcomponent copyrights and license notices.
The upstream source URLs were checked successfully during local packaging.
Build-only tools (pytest, Ruff, setuptools, packaging and hooks) are not application imports;
their versions are fixed in requirements-dev.lock. This is a component inventory, not legal advice.
Pillow 12.1.0 (HPND and bundled notices) is used only by the visual QA/GIF capture script,
not imported by the application and not part of the frozen runtime dependency set.
