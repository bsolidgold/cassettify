from __future__ import annotations
import spotipy
from cassettify.config import Config
from cassettify.auth import get_client
from cassettify.spotify import get_playlists, get_tracks, Playlist
from cassettify import cache
from cassettify.downloader import download_track
from cassettify.ui.wizard import WizardApp
from cassettify.ui.picker import PickerApp
from cassettify.ui.progress import ProgressApp


def run_wizard() -> Config:
    """Run the first-run setup wizard. Saves and returns Config."""
    import typer
    result = WizardApp().run()
    if result is None:
        typer.echo("Setup cancelled.")
        raise typer.Exit(code=0)
    config = Config(
        client_id=result.client_id,
        client_secret=result.client_secret,
        output_dir=result.output_dir,
    )
    config.save()
    return config


def run_picker(sp: spotipy.Spotify) -> list[Playlist]:
    """Run the interactive playlist picker. Returns selected playlists."""
    playlists = get_playlists(sp)
    if not playlists:
        return []
    return PickerApp(playlists).run() or []


def run_downloads(
    sp: spotipy.Spotify, playlists: list[Playlist], output_dir: str
) -> None:
    """Collect tracks from playlists, skip cached, run the progress UI."""
    all_tracks = []
    for playlist in playlists:
        tracks = get_tracks(sp, playlist.id)
        new = [t for t in tracks if not cache.contains(t.id)]
        all_tracks.extend(new)

    if not all_tracks:
        print("Nothing new to download — all tracks already in cache.")
        return

    def download_and_cache(track):
        success = download_track(track, output_dir)
        if success:
            cache.add(track.id)
        return success

    ProgressApp(all_tracks, download_and_cache).run()
