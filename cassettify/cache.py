from __future__ import annotations
import json
from pathlib import Path

CACHE_FILE = Path.home() / ".cassettify" / "cache.json"


def load() -> set[str]:
    if not CACHE_FILE.exists():
        return set()
    return set(json.loads(CACHE_FILE.read_text()))


def add(track_id: str) -> None:
    ids = load()
    ids.add(track_id)
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(sorted(ids), indent=2))


def contains(track_id: str) -> bool:
    return track_id in load()
