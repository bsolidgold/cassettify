from __future__ import annotations
import stat
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from cassettify.config import Config, CONFIG_DIR

SCOPE = "playlist-read-private playlist-read-collaborative"
_CACHE_PATH = str(CONFIG_DIR / ".spotify_cache")


def get_client(config: Config) -> spotipy.Spotify:
    auth_manager = SpotifyOAuth(
        client_id=config.client_id,
        client_secret=config.client_secret,
        redirect_uri="https://bsolidgold.github.io/cassettify/callback/",
        scope=SCOPE,
        cache_path=_CACHE_PATH,
        open_browser=True,
    )
    client = spotipy.Spotify(auth_manager=auth_manager)
    _secure_cache_file()
    return client


def _secure_cache_file() -> None:
    from pathlib import Path
    cache = Path(_CACHE_PATH)
    if cache.exists():
        cache.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
