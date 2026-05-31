from __future__ import annotations
import requests
from io import BytesIO
from typing import Callable
from textual.app import App, ComposeResult
from textual.widgets import Static, ProgressBar, Header, Footer, Label
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual import work
from cassettify.spotify import Track
from cassettify.downloader import download_track as _download_track


def _fetch_art(url: str, cols: int = 24) -> object | None:
    """Fetch album art URL and return a rich_pixels Pixels object, or None."""
    try:
        from rich_pixels import Pixels
        from PIL import Image
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        # Terminal cells are ~2:1 height:width, so double the columns for square art
        img = img.resize((cols * 2, cols))
        return Pixels.from_image(img)
    except Exception:
        return None


class ProgressApp(App):

    TITLE = "cassettify"
    BINDINGS = [("q", "quit_app", "Quit")]

    CSS = """
    #art {
        width: 50;
        height: 13;
        content-align: center middle;
        border: solid $primary;
        color: $text-muted;
    }
    #track-info { height: 13; width: 1fr; padding: 1 2; }
    #track-name { text-style: bold; margin-bottom: 1; }
    #artist-album { color: $text-muted; margin-bottom: 1; }
    #spotdl-status { color: $warning; }
    #overall {
        margin: 1 2;
        height: 3;
        padding: 0 1;
    }
    #overall-label { color: $text-muted; margin-bottom: 0; }
    #done-list, #queue-list {
        height: 1fr;
        border: solid $surface;
        padding: 0 1;
        overflow-y: auto;
    }
    #done-panel, #queue-panel { height: 1fr; width: 1fr; margin: 0 1; }
    .panel-title { color: $text-muted; text-style: bold; height: 1; }
    .done-item { color: $success; }
    .fail-item { color: $error; }
    .queue-item { color: $text-muted; }
    """

    def __init__(
        self,
        tracks: list[Track],
        output_dir: str,
        on_success: Callable[[Track], None] | None = None,
    ) -> None:
        super().__init__()
        self._tracks = tracks
        self._output_dir = output_dir
        self._on_success = on_success

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Horizontal(
            Static("♫", id="art"),
            Vertical(
                Static("", id="track-name"),
                Static("", id="artist-album"),
                Static("", id="spotdl-status"),
                id="track-info",
            ),
        )
        yield Vertical(
            Static("", id="overall-label"),
            ProgressBar(total=len(self._tracks), show_eta=False, id="progress"),
            id="overall",
        )
        yield Horizontal(
            Vertical(
                Static("✓  Done", classes="panel-title"),
                ScrollableContainer(id="done-list"),
                id="done-panel",
            ),
            Vertical(
                Static(f"Queue  ({len(self._tracks)} tracks)", classes="panel-title", id="queue-title"),
                ScrollableContainer(id="queue-list"),
                id="queue-panel",
            ),
        )
        yield Footer()

    def on_mount(self) -> None:
        queue = self.query_one("#queue-list")
        for t in self._tracks:
            queue.mount(Label(f"  {t.artist} — {t.name}", classes="queue-item", id=f"q-{t.id}"))
        self._run_downloads()

    @work(thread=True)
    def _run_downloads(self) -> None:
        done = 0
        for track in self._tracks:
            self.app.call_from_thread(self._set_now_playing, track, done)
            if track.album_art_url:
                art = _fetch_art(track.album_art_url)
                self.app.call_from_thread(self._set_art, art)

            def on_status(line: str, t: Track = track) -> None:
                if line:
                    self.app.call_from_thread(
                        self.query_one("#spotdl-status", Static).update,
                        f"  {line[:80]}"
                    )

            success = _download_track(track, self._output_dir, on_status)
            if success and self._on_success:
                self._on_success(track)
            done += 1
            self.app.call_from_thread(self._mark_done, track, success, done)

        self.app.call_from_thread(self._show_complete, done)

    def _set_now_playing(self, track: Track, done: int) -> None:
        self.query_one("#track-name", Static).update(f"[bold]{track.name}[/bold]")
        self.query_one("#artist-album", Static).update(f"{track.artist}  ·  {track.album}")
        self.query_one("#spotdl-status", Static).update("  Searching...")
        self.query_one("#overall-label", Static).update(
            f"  Downloading track {done + 1} of {len(self._tracks)}"
        )
        # Remove from queue
        try:
            self.query_one(f"#q-{track.id}").remove()
        except Exception:
            pass
        remaining = len(self._tracks) - done - 1
        self.query_one("#queue-title", Static).update(f"Queue  ({remaining} remaining)")

    def _set_art(self, art: object | None) -> None:
        widget = self.query_one("#art", Static)
        widget.update(art if art is not None else "♫")

    def _mark_done(self, track: Track, success: bool, done: int) -> None:
        self.query_one("#progress", ProgressBar).advance(1)
        self.query_one("#spotdl-status", Static).update("")
        done_list = self.query_one("#done-list")
        if success:
            done_list.mount(Label(f"✓  {track.name}", classes="done-item"))
        else:
            done_list.mount(Label(f"✗  {track.name}", classes="fail-item"))

    def _show_complete(self, done: int) -> None:
        total = len(self._tracks)
        self.query_one("#track-name", Static).update(
            f"[bold green]All done![/bold green]  {done}/{total} downloaded"
        )
        self.query_one("#artist-album", Static).update("")
        self.query_one("#spotdl-status", Static).update("")
        self.query_one("#overall-label", Static).update("")
        self.query_one("#art", Static).update("♫")

    def action_quit_app(self) -> None:
        self.exit()
