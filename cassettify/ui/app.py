from __future__ import annotations
import spotipy
from cassettify.config import Config
from cassettify.spotify import Track
from cassettify.ui.wizard import WizardApp
from cassettify.ui.picker import CassettifyApp


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


def run_app(
    sp: spotipy.Spotify,
    output_dir: str,
    initial_tracks: list[Track] | None = None,
) -> None:
    """Launch the unified browse + download app."""
    CassettifyApp(sp, output_dir, initial_tracks).run()
