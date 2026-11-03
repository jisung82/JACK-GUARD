import json
from datetime import UTC, datetime, timedelta


class Events:
    def __init__(self, directory, retention=30):
        self.directory = directory
        self.retention = retention
        self.prune()

    def prune(self):
        cutoff = datetime.now(UTC).date() - timedelta(days=self.retention - 1)
        for path in self.directory.glob("events-*.jsonl"):
            try:
                date = datetime.strptime(path.stem[7:], "%Y-%m-%d").date()
                if date < cutoff:
                    path.unlink()
            except ValueError:
                continue

    def add(self, kind, detail=""):
        self.prune()
        now = datetime.now(UTC)
        path = self.directory / f"events-{now:%Y-%m-%d}.jsonl"
        # Bound daily volume. Never log passwords, keystrokes or full executable paths.
        if path.exists() and path.stat().st_size > 2_000_000:
            return
        with path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {"time": now.isoformat(), "event": kind, "detail": str(detail)[:160]},
                    ensure_ascii=False,
                )
                + "\n"
            )

    def read(self):
        lines = []
        for path in sorted(self.directory.glob("events-*.jsonl"), reverse=True):
            lines += path.read_text(encoding="utf-8", errors="replace").splitlines()[-500:][::-1]
            if len(lines) >= 500:
                break
        return "\n".join(lines[:500])

    def clear(self):
        for path in self.directory.glob("events-*.jsonl"):
            path.unlink()
