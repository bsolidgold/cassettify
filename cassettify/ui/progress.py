from __future__ import annotations
import asyncio
from typing import Callable
from textual.app import App, ComposeResult
from textual.widgets import (
    Static, ProgressBar, ListView, ListItem, Label, Header, Footer
)
from textual.containers import Horizontal, Vertical, Container
from textual.reactive import reactive
from cassettify.spotify import Track


class ProgressApp(App):
    """Download progress display. Calls download_fn(track) -> bool per track."""

    TITLE = "cassettify"
    BINDINGS = [("q", "quit_app", "Quit")]

    CSS = """
    #now-playing {
        height: 9;
        border: solid $primary;
        margin: 1 2;
        padding: 1 2;
    }
    #art {
        width: 10;
        height: 5;
        border: solid $primary;
        margin-right: 2;
        content-align: center middle;
        color: $text-muted;
    }
    #track-info { height: 5; width: 1fr; }
    #track-name { text-style: bold; }
    #artist-album { color: $text-muted; margin-bottom: 1; }
    #panels { height: 1fr; margin: 0 2; }
    #queue-panel, #done-panel { height: 1fr; width: 1fr; border: solid $surface; padding: 1; }
    .panel-title { color: $text-muted; margin-bottom: 1; }
    .done-label { color: $success; }
    .fail-label { color: $error; }
    """

    def __init__(self, tracks: list[Track], download_fn: Callable[[Track], bool]) -> None:
        super().__init__()
        self._tracks = tracks
        self._download_fn = download_fn

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Container(
            Horizontal(
                Static("♫", id="art"),
                Vertical(
                    Static("Preparing...", id="track-name"),
                    Static("", id="artist-album"),
                    ProgressBar(total=len(self._tracks), show_eta=False, id="progress"),
                    id="track-info",
                ),
                id="now-playing",
            ),
        )
        yield Horizontal(
            Vertical(
                Static(f"Queue ({len(self._tracks)} tracks)", classes="panel-title", id="queue-title"),
                ListView(id="queue"),
                id="queue-panel",
            ),
            Vertical(
                Static("✓ Done", classes="panel-title"),
                ListView(id="done"),
                id="done-panel",
            ),
            id="panels",
        )
        yield Footer()

    def on_mount(self) -> None:
        queue = self.query_one("#queue", ListView)
        for t in self._tracks:
            queue.append(ListItem(Label(f"  {t.artist} — {t.name}"), id=f"q-{t.id}"))
        self.run_worker(self._run_downloads())

    async def _run_downloads(self) -> None:
        done_count = 0
        for track in self._tracks:
            self.query_one("#track-name", Static).update(f"[bold]{track.name}[/bold]")
            self.query_one("#artist-album", Static).update(
                f"{track.artist}  ·  {track.album}"
            )
            try:
                self.query_one(f"#q-{track.id}").remove()
            except Exception:
                pass
            remaining = len(self._tracks) - done_count - 1
            self.query_one("#queue-title", Static).update(
                f"Queue ({remaining} remaining)"
            )

            success = await asyncio.to_thread(self._download_fn, track)
            done_count += 1
            self.query_one("#progress", ProgressBar).advance(1)

            done_list = self.query_one("#done", ListView)
            if success:
                await done_list.append(ListItem(Label(f"✓ {track.name}", classes="done-label")))
            else:
                await done_list.append(ListItem(Label(f"✗ {track.name}", classes="fail-label")))

        self.query_one("#track-name", Static).update(
            f"[bold green]All done![/bold green]  {done_count}/{len(self._tracks)} tracks downloaded"
        )
        self.query_one("#artist-album", Static).update("Press Q to quit")

    def action_quit_app(self) -> None:
        self.exit()
