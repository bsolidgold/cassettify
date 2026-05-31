from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from cassettify.spotify import Track

FAILED_LOG = Path.home() / ".cassettify" / "failed.log"

_OUTPUT_TEMPLATE = "{artists}/{album}/{track-number} - {title}.{output-ext}"


def download_track(track: Track, output_dir: str) -> bool:
    """Download a single track via spotdl. Returns True on success."""
    full_template = str(Path(output_dir) / _OUTPUT_TEMPLATE)
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "spotdl",
                track.spotify_url,
                "--output", full_template,
                "--format", "mp3",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            _log_failure(track, result.stderr.strip())
            return False
        return True
    except subprocess.TimeoutExpired:
        _log_failure(track, "timeout after 120s")
        return False
    except Exception as e:
        _log_failure(track, str(e))
        return False


def _log_failure(track: Track, reason: str) -> None:
    FAILED_LOG.parent.mkdir(exist_ok=True)
    with FAILED_LOG.open("a") as f:
        f.write(f"{track.artist} - {track.name} ({track.id}): {reason}\n")
