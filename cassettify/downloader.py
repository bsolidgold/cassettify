from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable
from cassettify.spotify import Track

FAILED_LOG = Path.home() / ".cassettify" / "failed.log"
COOKIE_FILE = Path.home() / ".cassettify" / "cookies.txt"
_OUTPUT_TEMPLATE = "{artists}/{album}/{track-number} - {title}.{output-ext}"


def download_track(
    track: Track,
    output_dir: str,
    status_cb: Callable[[str], None] | None = None,
) -> bool:
    """Download a single track via spotdl. Streams status lines to status_cb."""
    full_template = str(Path(output_dir) / _OUTPUT_TEMPLATE)
    cmd = [
        sys.executable, "-u", "-m", "spotdl",
        track.spotify_url,
        "--output", full_template,
        "--format", "mp3",
        "--max-retries", "3",
    ]
    if COOKIE_FILE.exists():
        cmd += ["--cookie-file", str(COOKIE_FILE)]
    try:
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        for line in proc.stdout:
            line = line.strip()
            if line and status_cb:
                status_cb(_clean_status(line))
        proc.wait(timeout=300)
        if proc.returncode != 0:
            _log_failure(track, f"exit code {proc.returncode}")
            return False
        return True
    except subprocess.TimeoutExpired:
        proc.kill()
        _log_failure(track, "timeout after 300s")
        return False
    except Exception as e:
        _log_failure(track, str(e))
        return False


def _clean_status(line: str) -> str:
    """Strip ANSI codes and log prefixes from spotdl output."""
    import re
    line = re.sub(r'\x1b\[[0-9;]*m', '', line)
    for prefix in ("INFO", "WARNING", "ERROR", "DEBUG", "spotdl"):
        if line.startswith(prefix):
            line = line[len(prefix):].lstrip(" :-|")
    return line.strip()


def _log_failure(track: Track, reason: str) -> None:
    FAILED_LOG.parent.mkdir(exist_ok=True)
    with FAILED_LOG.open("a") as f:
        f.write(f"{track.artist} - {track.name} ({track.id}): {reason}\n")
