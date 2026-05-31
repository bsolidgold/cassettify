from __future__ import annotations
import spotipy
from cassettify.config import Config
from cassettify.spotify import get_all_sources, get_tracks_for_source, Track, Playlist
from cassettify import cache
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


def run_picker(sp: spotipy.Spotify) -> list[Track]:
    """Run the interactive picker. Returns selected tracks."""
    result = PickerApp(sp).run()
    return result or []


def run_downloads(tracks: list[Track], output_dir: str) -> None:
    """Filter cached tracks then run the progress UI."""
    new_tracks = [t for t in tracks if not cache.contains(t.id)]
    if not new_tracks:
        print("Nothing new to download — all tracks already in cache.")
        return

    def on_success(track: Track) -> None:
        cache.add(track.id)

    ProgressApp(new_tracks, output_dir, on_success).run()
