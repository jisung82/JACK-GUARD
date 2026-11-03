import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from jack_guard.security.passwords import valid_record


@dataclass
class Settings:
    lock_hotkey: str = "Ctrl+Alt+L"
    privacy_hotkey: str = "Ctrl+Alt+P"
    monitor: bool = False
    notifications: bool = True
    overlay: bool = False
    terminate: bool = False
    games: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    retention_days: int = 30
    password: dict = field(default_factory=dict)


def validate(data):
    if not isinstance(data, dict) or set(data) - set(asdict(Settings())):
        raise ValueError("알 수 없는 설정 형식")
    result = Settings(**data)
    for key in ("monitor", "notifications", "overlay", "terminate"):
        if type(getattr(result, key)) is not bool:
            raise ValueError("잘못된 설정 값")
    for key in ("games", "exceptions"):
        paths = getattr(result, key)
        if not isinstance(paths, list) or len(paths) > 100:
            raise ValueError("실행파일 목록은 최대 100개입니다.")
        if any(
            not isinstance(p, str)
            or len(p) > 32760
            or not Path(p).is_absolute()
            or Path(p).suffix.lower() != ".exe"
            for p in paths
        ):
            raise ValueError("전체 .exe 경로를 지정하세요.")
    if type(result.retention_days) is not int or not 1 <= result.retention_days <= 365:
        raise ValueError("로그 보존 기간: 1~365일")
    from jack_guard.core.hotkeys import parse_hotkey

    parse_hotkey(result.lock_hotkey)
    parse_hotkey(result.privacy_hotkey)
    if parse_hotkey(result.lock_hotkey) == parse_hotkey(result.privacy_hotkey):
        raise ValueError("두 단축키가 같습니다.")
    if not isinstance(result.password, dict) or (
        result.password and not valid_record(result.password)
    ):
        raise ValueError("잘못된 비밀번호 레코드")
    return result


def secure_directory(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.is_junction():
        raise OSError("설정 폴더는 링크일 수 없습니다.")
    if sys.platform == "win32":
        from jack_guard.security.windows import current_sid

        subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"*{current_sid()}:(OI)(CI)F",
                "*S-1-5-18:(OI)(CI)F",
            ],
            check=True,
            capture_output=True,
            creationflags=0x08000000,
        )
    else:
        path.chmod(0o700)


class Store:
    def __init__(self, directory: Path):
        self.directory = directory
        secure_directory(directory)
        self.path = directory / "settings.json"
        self.recovered = False

    def load(self):
        if not self.path.exists():
            return Settings()
        try:
            if self.path.stat().st_size > 1_000_000:
                raise ValueError("설정 파일 크기 초과")
            return validate(json.loads(self.path.read_text(encoding="utf-8")))
        except (ValueError, TypeError, UnicodeError):
            # Never silently discard a password or enable actions after corruption.
            self.recovered = True
            raise ValueError(
                "설정 파일 손상. --reset-settings로 명시적으로 초기화하세요."
            ) from None

    def save(self, settings):
        data = asdict(validate(asdict(settings)))
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

    def export(self, settings, path):
        data = asdict(settings)
        data["password"] = {}
        data["terminate"] = False
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def import_file(self, path, password):
        if Path(path).stat().st_size > 1_000_000:
            raise ValueError("설정 파일 크기 초과")
        result = validate(json.loads(Path(path).read_text(encoding="utf-8")))
        result.password = password
        result.terminate = False
        result.monitor = False
        return result
