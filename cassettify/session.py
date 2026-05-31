from __future__ import annotations
import json
import os
from dataclasses import asdict
from pathlib import Path
from cassettify.spotify import Track

SESSION_FILE = Path.home() / ".cassettify" / "session.json"

# Leftover temp files spotdl / yt-dlp / ffmpeg create mid-download
_PARTIAL_GLOBS = ("*.part", "*.ytdl", "*.temp", "*.tmp", "*.part-*", "*.spotdl")


def save_pending(tracks: list[Track]) -> None:
    """Persist the not-yet-downloaded queue so it can resume after a stop/crash."""
    SESSION_FILE.parent.mkdir(exist_ok=True)
    tmp = SESSION_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps([asdict(t) for t in tracks], indent=2))
    os.replace(tmp, SESSION_FILE)


def load_pending() -> list[Track]:
    if not SESSION_FILE.exists():
        return []
    try:
        return [Track(**d) for d in json.loads(SESSION_FILE.read_text())]
    except Exception:
        return []


def clear() -> None:
    try:
        SESSION_FILE.unlink()
    except FileNotFoundError:
        pass


def cleanup_partials(output_dir: str) -> int:
    """Remove partial/temp download files left behind by an interrupted run."""
    d = Path(output_dir).expanduser()
    if not d.exists():
        return 0
    removed = 0
    for pattern in _PARTIAL_GLOBS:
        for f in d.rglob(pattern):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
    return removed
