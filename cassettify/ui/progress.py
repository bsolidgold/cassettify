from __future__ import annotations
from typing import Callable
from textual.app import App, ComposeResult
from textual.widgets import Static, Header, Footer, Label
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual import work
from cassettify.spotify import Track
from cassettify.downloader import download_track as _dl

# ── Cassette art ──────────────────────────────────────────────────────────────

_LS = "─╲│╱"
_RS = "─╱│╲"


def _fit(s: str, w: int) -> str:
    return (s[:w - 1] + "…") if len(s) > w else s.ljust(w)


def _cassette(
    name: str, artist: str, album: str,
    done: int, total: int,
    status: str, tick: int, spinning: bool,
) -> str:
    lsp = _LS[tick % 4] if spinning else "·"
    rsp = _RS[tick % 4] if spinning else "·"

    n  = _fit(name,   20)
    a  = _fit(artist, 20)
    b  = _fit(album,  20)
    ti = _fit(f"track {done} of {total}", 16)
    st = _fit(status or "", 52)

    BAR = 26
    filled = int(done / max(total, 1) * BAR)
    bar = "▓" * filled + "░" * (BAR - filled)
    pct = f"{int(done / max(total, 1) * 100)}%".rjust(4)

    HDR = _fit("  C A S S E T T I F Y           S I D E  A", 50)

    return "\n".join([
        f"  ╔{'═' * 56}╗",
        f"  ║  ┌{'─' * 50}┐  ║",
        f"  ║  │{HDR}│  ║",
        f"  ║  └{'─' * 50}┘  ║",
        f"  ║{' ' * 56}║",
        f"  ║  ╭────────╮   ╔{'═' * 24}╗   ╭────────╮  ║",
        f"  ║  │ ╭────╮ │   ║  {n}  ║   │ ╭────╮ │  ║",
        f"  ║  │ │  {lsp} │ │   ║  {a}  ║   │ │  {rsp} │ │  ║",
        f"  ║  │ ╰────╯ │   ║  {b}  ║   │ ╰────╯ │  ║",
        f"  ║  ╰────────╯   ╚{'═' * 24}╝   ╰────────╯  ║",
        f"  ║{' ' * 56}║",
        f"  ║  {ti}   {bar}   {pct}  ║",
        f"  ║  {st}  ║",
        f"  ╚{'═' * 56}╝",
    ])


# ── App ───────────────────────────────────────────────────────────────────────

class ProgressApp(App):

    TITLE = "cassettify"
    BINDINGS = [("q", "quit_app", "Quit")]

    CSS = """
    #cassette {
        height: 16;
        width: 100%;
        content-align: center middle;
        color: $primary;
        text-style: bold;
    }
    #panels { height: 1fr; margin: 0 2; }
    #done-panel, #queue-panel { height: 1fr; width: 1fr; margin: 0 1; }
    .panel-title { height: 1; text-style: bold; color: $text-muted; padding: 0 1; }
    #done-list, #queue-list {
        height: 1fr;
        border: solid $surface;
        padding: 0 1;
        overflow-y: auto;
    }
    .done-item  { color: $success; }
    .fail-item  { color: $error; }
    .queue-item { color: $text-muted; }
    """

    def __init__(
        self,
        tracks: list[Track],
        output_dir: str,
        on_success: Callable[[Track], None] | None = None,
    ) -> None:
        super().__init__()
        self._tracks     = tracks
        self._output_dir = output_dir
        self._on_success = on_success
        self._cur_name   = ""
        self._cur_artist = ""
        self._cur_album  = ""
        self._cur_status = ""
        self._done       = 0
        self._spinning   = False
        self._tick       = 0
        self._finished   = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(
            _cassette("", "", "", 0, len(self._tracks), "", 0, False),
            id="cassette",
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
            id="panels",
        )
        yield Footer()

    def on_mount(self) -> None:
        queue = self.query_one("#queue-list")
        for t in self._tracks:
            queue.mount(Label(f"  {t.artist} — {t.name}", classes="queue-item", id=f"q-{t.id}"))
        self.set_interval(0.12, self._animate)
        self._run_all()

    def _animate(self) -> None:
        self._tick += 1
        self.query_one("#cassette", Static).update(
            _cassette(
                self._cur_name, self._cur_artist, self._cur_album,
                self._done, len(self._tracks),
                self._cur_status, self._tick, self._spinning,
            )
        )

    @work(thread=True)
    def _run_all(self) -> None:
        for track in self._tracks:
            self._cur_name   = track.name
            self._cur_artist = track.artist
            self._cur_album  = track.album
            self._cur_status = "Searching…"
            self._spinning   = True

            self.app.call_from_thread(self._remove_from_queue, track)

            def on_status(line: str) -> None:
                if line:
                    self._cur_status = line[:58]

            success = _dl(track, self._output_dir, on_status)

            if success and self._on_success:
                self._on_success(track)

            self._done += 1
            self.app.call_from_thread(self._add_to_done, track, success)

        self._finished   = True
        self._spinning   = False
        self._cur_name   = "All done!"
        self._cur_artist = f"{self._done} tracks downloaded"
        self._cur_album  = ""
        self._cur_status = "Press Q to quit"

    def _remove_from_queue(self, track: Track) -> None:
        remaining = len(self._tracks) - self._done - 1
        self.query_one("#queue-title", Static).update(f"Queue  ({remaining} remaining)")
        try:
            self.query_one(f"#q-{track.id}").remove()
        except Exception:
            pass

    def _add_to_done(self, track: Track, success: bool) -> None:
        self.query_one("#done-list").mount(
            Label(
                f"✓  {track.name}" if success else f"✗  {track.name}",
                classes="done-item" if success else "fail-item",
            )
        )

    def action_quit_app(self) -> None:
        self.exit()
