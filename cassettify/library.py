from __future__ import annotations
import shutil
from pathlib import Path
from typing import Callable

_AUDIO_EXTS = {".mp3", ".m4a", ".opus", ".flac", ".ogg", ".wav"}


def count_tracks(directory: str) -> int:
    """Count audio files under a directory (recursively)."""
    d = Path(directory).expanduser()
    if not d.exists():
        return 0
    return sum(1 for f in d.rglob("*") if f.is_file() and f.suffix.lower() in _AUDIO_EXTS)


def move_library(
    old_dir: str,
    new_dir: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> tuple[int, int]:
    """Move every file from old_dir into new_dir, preserving the Artist/Album tree.

    Files already present at the destination are skipped (not overwritten).
    Returns (moved, skipped). Empty directories left behind are cleaned up.
    """
    old = Path(old_dir).expanduser()
    new = Path(new_dir).expanduser()
    if not old.exists() or old.resolve() == new.resolve():
        return 0, 0

    files = [f for f in old.rglob("*") if f.is_file()]
    total = len(files)
    moved = skipped = 0
    for i, f in enumerate(files):
        dest = new / f.relative_to(old)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            skipped += 1
        else:
            shutil.move(str(f), str(dest))
            moved += 1
        if progress_cb:
            progress_cb(i + 1, total)

    # Remove now-empty directories under old (deepest first)
    for d in sorted((p for p in old.rglob("*") if p.is_dir()), reverse=True):
        try:
            d.rmdir()
        except OSError:
            pass
    return moved, skipped
