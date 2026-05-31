from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer
from cassettify.config import Config
from cassettify.auth import get_client
from cassettify.spotify import get_playlists, get_tracks, find_playlist_by_name
from cassettify.ui.app import run_wizard, run_app

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


def _set_output(path: Path) -> None:
    from cassettify import library
    config = Config.load()
    if config is None:
        typer.echo("No config yet — run 'cassettify' once to set up first.", err=True)
        raise typer.Exit(code=1)
    old = config.output_dir
    new = str(path.expanduser())
    if old == new:
        typer.echo(f"Output directory is already {new}.")
        return
    typer.echo(f"Current: {old}")
    typer.echo(f"New:     {new}")
    config.output_dir = new
    config.save()
    typer.echo("✓ Default updated.")

    n = library.count_tracks(old)
    if n and typer.confirm(f"Move {n} existing track(s) from the old folder to the new one?"):
        moved, skipped = library.move_library(old, new)
        typer.echo(f"✓ Moved {moved} file(s)" + (f", skipped {skipped} already present" if skipped else ""))


def _grab_cookies(browser: Optional[str]) -> None:
    from cassettify import cookies as ck
    typer.echo("Grabbing YouTube cookies (your browser or keychain may ask for permission)...")
    found = ck.extract(browser)
    if found:
        typer.echo(f"✓ Saved {found} cookies to {ck.COOKIE_FILE}")
    else:
        typer.echo("Couldn't read cookies from any browser. Downloads will still work but may hit rate limits.", err=True)


def _ensure_cookies() -> None:
    """On first run, try to auto-grab cookies so downloads aren't rate-limited."""
    from cassettify import cookies as ck
    if ck.COOKIE_FILE.exists():
        return
    typer.echo("Setting up YouTube access for downloads (your browser/keychain may prompt)...")
    found = ck.extract()
    if found:
        typer.echo(f"✓ Using {found} cookies — downloads won't be rate-limited.")
    else:
        typer.echo("(No browser cookies found — that's fine, but you may hit YouTube rate limits.")
        typer.echo(" You can retry later with: cassettify --cookies auto)")


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
    cookies: Optional[str] = typer.Option(
        None, "--cookies",
        help="Grab YouTube cookies from a browser (chrome/safari/firefox/edge/brave/... or 'auto') and exit",
    ),
    set_output: Optional[Path] = typer.Option(
        None, "--set-output",
        help="Change where music is saved (offers to move your existing library) and exit",
    ),
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    if set_output is not None:
        _set_output(set_output)
        return

    if setup:
        config = Config.load()
        run_wizard(config)
        return

    if cookies is not None:
        _grab_cookies(None if cookies in ("", "auto") else cookies)
        return

    config = _ensure_config()
    output_dir = str(output) if output else config.output_dir
    _ensure_cookies()
    sp = get_client(config)

    if all_playlists:
        playlists = get_playlists(sp)
        tracks = []
        for pl in playlists:
            tracks.extend(get_tracks(sp, pl.id))
        run_app(sp, output_dir, tracks)
    elif playlist:
        all_pls = get_playlists(sp)
        match = find_playlist_by_name(all_pls, playlist)
        if not match:
            typer.echo(f"Playlist '{playlist}' not found.", err=True)
            raise typer.Exit(code=1)
        run_app(sp, output_dir, get_tracks(sp, match.id))
    else:
        run_app(sp, output_dir)
