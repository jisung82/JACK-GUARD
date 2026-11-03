import os
from pathlib import Path

import psutil

DENIED = {
    "system",
    "registry",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "winlogon.exe",
    "lsass.exe",
    "services.exe",
    "svchost.exe",
    "explorer.exe",
    "dwm.exe",
    "fontdrvhost.exe",
    "sihost.exe",
    "taskhostw.exe",
    "jack-guard.exe",
}


def normalized(path):
    return os.path.normcase(os.path.realpath(path))


def safe_target(pid, path):
    if pid <= 4 or pid == os.getpid() or Path(path).name.lower() in DENIED:
        return False
    try:
        if pid in {p.pid for p in psutil.Process().parents()}:
            return False
    except psutil.Error:
        return False
    windows = normalized(os.environ.get("SystemRoot", r"C:\Windows"))
    candidate = normalized(path)
    return not (candidate == windows or candidate.startswith(windows + os.sep))


class ProcessMonitor:
    def __init__(self):
        self.seen = set()

    def scan(self, settings, processes=None):
        if not settings.monitor:
            self.seen.clear()
            return []
        games = {normalized(p) for p in settings.games}
        exceptions = {normalized(p) for p in settings.exceptions}
        current, events = set(), []
        if processes is None:
            processes = psutil.process_iter(["pid", "exe", "create_time"])
        for proc in processes:
            try:
                info = proc.info
                if not info["exe"]:
                    continue
                path = normalized(info["exe"])
                if path not in games or path in exceptions:
                    continue
                identity = (info["pid"], info["create_time"])
                current.add(identity)
                if identity in self.seen:
                    continue
                event = {"pid": info["pid"], "name": Path(path).name, "action": "감지"}
                if settings.terminate:
                    if not safe_target(info["pid"], path):
                        event["action"] = "종료 거부: 보호 대상"
                    else:
                        try:
                            from jack_guard.security.windows import terminate_owned

                            terminate_owned(info["pid"], path)
                            event["action"] = "종료 요청 완료"
                        except (OSError, ValueError):
                            event["action"] = "종료 거부: 권한 또는 상태 확인 실패"
                events.append(event)
            except (psutil.Error, OSError):
                continue
        self.seen = current
        return events
