"""Copy only notices from caller-supplied, official Qt 6.10.2 source archives."""

import hashlib
import json
import sys
import tarfile
from pathlib import Path


def main():
    output = Path(__file__).resolve().parents[1] / "docs" / "licenses" / "qt"
    output.mkdir(parents=True, exist_ok=True)
    provenance = []
    for argument in sys.argv[1:]:
        archive = Path(argument)
        with archive.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        count = 0
        with tarfile.open(archive, "r:xz") as package:
            for member in package:
                relative = Path(*Path(member.name).parts[1:])
                base = relative.name.lower()
                notice = (
                    "licenses" in [p.lower() for p in relative.parts]
                    or base.startswith(("license", "copying", "copyright"))
                    or base == "qt_attribution.json"
                    or ("3rdparty" in relative.parts and base.startswith("readme"))
                )
                if not member.isfile() or not notice or member.size > 2_000_000:
                    continue
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Unsafe archive path")
                destination = output / archive.stem.split(".")[0] / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with package.extractfile(member) as source:
                    destination.write_bytes(source.read())
                count += 1
        provenance.append(
            {
                "archive": archive.name,
                "sha256": checksum,
                "notices": count,
                "version": "6.10.2",
                "source": "https://download.qt.io/archive/qt/6.10/6.10.2/submodules/",
            }
        )
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
