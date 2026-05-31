from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer
from cassettify.config import Config
from cassettify.auth import get_client
from cassettify.spotify import get_playlists, get_tracks, find_playlist_by_name
from cassettify.ui.app import run_wizard, run_picker, run_downloads

app = typer.Typer(
    name="cassettify",
    help="Download your Spotify playlists for your iPod Classic.",
    add_completion=False,
)


def _ensure_config() -> Config:
    config = Config.load()
    if config is None:
        typer.echo("First time setup — let's connect Spotify.")
        config = run_wizard()
    return config


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    playlist: Optional[str] = typer.Argument(
        None, help="Name of a playlist to download (skips the picker)"
    ),
    all_playlists: bool = typer.Option(
        False, "--all", "-a", help="Download every playlist"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory (overrides saved default)"
    ),
    setup: bool = typer.Option(
        False, "--setup", help="Re-run the first-time setup wizard"
    ),
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    if setup:
        run_wizard()
        return

    config = _ensure_config()
    output_dir = str(output) if output else config.output_dir
    sp = get_client(config)

    if all_playlists:
        playlists = get_playlists(sp)
        tracks = []
        for pl in playlists:
            tracks.extend(get_tracks(sp, pl.id))
    elif playlist:
        all_pls = get_playlists(sp)
        match = find_playlist_by_name(all_pls, playlist)
        if not match:
            typer.echo(f"Playlist '{playlist}' not found.", err=True)
            raise typer.Exit(code=1)
        tracks = get_tracks(sp, match.id)
    else:
        tracks = run_picker(sp)
        if not tracks:
            return

    run_downloads(tracks, output_dir)
