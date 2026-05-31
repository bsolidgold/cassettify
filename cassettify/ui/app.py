from __future__ import annotations
import spotipy
from cassettify.config import Config
from cassettify.spotify import Track
from cassettify.ui.wizard import WizardApp
from cassettify.ui.picker import CassettifyApp


def run_wizard(existing: Config | None = None) -> Config:
    """Run the first-run setup wizard. Saves and returns Config.

    If `existing` is given (re-running setup), the wizard pre-fills the current
    output dir and can offer to move the existing library to a new location.
    """
    import typer
    from cassettify import library

    old_dir = existing.output_dir if existing else None
    result = WizardApp(existing_dir=old_dir).run()
    if result is None:
        typer.echo("Setup cancelled.")
        raise typer.Exit(code=0)
    config = Config(
        client_id=result.client_id,
        client_secret=result.client_secret,
        output_dir=result.output_dir,
    )
    config.save()

    if result.move_existing and old_dir and old_dir != result.output_dir:
        typer.echo(f"Moving your library to {result.output_dir} ...")
        moved, skipped = library.move_library(old_dir, result.output_dir)
        typer.echo(f"✓ Moved {moved} file(s)" + (f", skipped {skipped} already present" if skipped else ""))

    return config


def run_app(
    sp: spotipy.Spotify,
    output_dir: str,
    initial_tracks: list[Track] | None = None,
) -> None:
    """Launch the unified browse + download app."""
    CassettifyApp(sp, output_dir, initial_tracks).run()
