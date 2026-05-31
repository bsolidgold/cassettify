from __future__ import annotations
import re
import time
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Header, Footer
from textual.containers import Horizontal, Vertical, ScrollableContainer

# ── Status interpretation ─────────────────────────────────────────────────────

_PCT = re.compile(r"(\d{1,3}(?:\.\d)?)%")


def _interpret(line: str) -> str | None:
    """Map raw spotdl/yt-dlp output to a clean, human phase. None = ignore."""
    low = line.lower()
    if "[download]" in low:
        m = _PCT.search(line)
        if m:
            return f"Downloading…  {int(float(m.group(1)))}%"
        return "Downloading…"
    if "processing query" in low:
        return "Looking up track…"
    if "searching" in low:
        return "Searching YouTube Music…"
    if "downloading song" in low or ("downloading" in low and "using" in low):
        return "Downloading audio…"
    if "fetching lyrics" in low or "found lyrics" in low:
        return "Fetching lyrics…"
    if "converting" in low or "ffmpeg" in low:
        return "Converting to MP3…"
    if "applied metadata" in low or "embedding" in low:
        return "Tagging & embedding art…"
    if "skipping" in low or "already has metadata" in low or "already exists" in low:
        return "Already downloaded — skipping"
    if "could not find a match" in low or "could not find metadata" in low:
        return "No match found"
    if "error downloading" in low or "failure downloading" in low or "blocked" in low:
        return "Hit a snag — retrying…"
    return None


# ── Cassette art ──────────────────────────────────────────────────────────────
# Modeled on a real compact cassette: the printed label fills the whole face
# (side badge, title, underline, artist/album up top), and the two small reels
# sit close together in the center with the tape window between them. The iconic
# bottom stripe doubles as the download progress bar.

_INNER = 88           # content width between the outer shell walls
_LC = _INNER - 6      # label inner width
_GAP = " " * 8        # spacing that sets the reels apart around the tape window

# Rotating reel hub spokes — 5 wide, 3 tall, narrow glyphs only (no wide unicode)
_SPOKES = [
    ["  │  ", "──┼──", "  │  "],
    [" ╲ ╱ ", "  ┼  ", " ╱ ╲ "],
    ["  │  ", "──┼──", "  │  "],
    [" ╱ ╲ ", "  ┼  ", " ╲ ╱ "],
]
# Tape window between the reels — 9 wide, 5 tall
_TAPE = ["┌───────┐", "│▓▓▓▓▓▓▓│", "│░░░░░░░│", "│▓▓▓▓▓▓▓│", "└───────┘"]


def _fit(s: str, w: int) -> str:
    return (s[:w - 1] + "…") if len(s) > w else s.ljust(w)


def _center(s: str, w: int) -> str:
    s = s[:w]
    pad = w - len(s)
    left = pad // 2
    return " " * left + s + " " * (pad - left)


def _reel(frame: int) -> list[str]:
    return ["╭───────╮"] + [f"│ {r} │" for r in _SPOKES[frame]] + ["╰───────╯"]


def _cassette(name, artist, album, done, total, status, tick, spinning) -> str:
    frame = tick % 4 if spinning else 2
    lr = _reel(frame)
    rr = _reel((frame + 2) % 4)
    bar_w = _LC - 14
    filled = int(done / max(total, 1) * bar_w)
    bar = "▓" * filled + "░" * (bar_w - filled)
    pct = f"{int(done / max(total, 1) * 100)}%".rjust(4)
    band = [lr[i] + _GAP + _TAPE[i] + _GAP + rr[i] for i in range(5)]
    meta = artist + ("  ·  " + album if album else "")

    def shell(c: str) -> str:
        return f"  ║{c[:_INNER].ljust(_INNER)}║"

    def label(inner: str) -> str:
        return shell("   │" + _fit(inner, _LC - 2) + "│   ")

    screws = shell(" o" + " " * (_INNER - 4) + "o ")
    lines = [
        "  ╔" + "═" * _INNER + "╗",
        screws,
        shell("   ┌" + "─" * (_LC - 2) + "┐   "),
        label(" [A]"),
        label("  " + name),
        label("  " + "─" * (_LC - 6)),
        label("  " + meta),
        label(""), label(""), label(""),
        *[label(_center(b, _LC - 2)) for b in band],
        label(""), label(""), label(""),
        label("  " + _fit(status or "", _LC - 26) + f"   track {done}/{total}"),
        label("  " + bar + "  " + pct),
        shell("   └" + "─" * (_LC - 2) + "┘   "),
        screws,
        "  ╚" + "═" * _INNER + "╝",
    ]
    return "\n".join(lines)


# ── Download screen (stateless view over app download state) ──────────────────

class DownloadScreen(Screen):

    CSS = """
    #cassette {
        height: 24;
        width: 100%;
        content-align: center middle;
        color: $primary;
        text-style: bold;
    }
    #panels { height: 1fr; margin: 0 2; }
    #queue-panel, #done-panel { height: 1fr; width: 1fr; margin: 0 1; }
    .panel-title { height: 1; text-style: bold; color: $text-muted; padding: 0 1; }
    #queue-list, #done-list {
        height: 1fr;
        border: solid $surface;
        padding: 0 1;
        overflow-y: auto;
    }
    #queue-text { color: $text-muted; }
    #done-text { color: $success; }
    #outdir { dock: bottom; height: 1; color: $text-muted; padding: 0 2; }
    """

    BINDINGS = [
        ("escape", "go_back", "Back to library"),
        ("q", "quit_app", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("", id="cassette", markup=False)
        yield Horizontal(
            Vertical(
                Static("Queue", classes="panel-title", id="queue-title"),
                ScrollableContainer(Static("", id="queue-text", markup=False), id="queue-list"),
                id="queue-panel",
            ),
            Vertical(
                Static("✓  Done", classes="panel-title"),
                ScrollableContainer(Static("", id="done-text", markup=False), id="done-list"),
                id="done-panel",
            ),
            id="panels",
        )
        yield Static("", id="outdir")
        yield Footer()

    def on_mount(self) -> None:
        from cassettify.ui.picker import _short
        self.query_one("#outdir", Static).update(f"⤓ Saving to: {_short(self.app._output_dir)}")
        self.set_interval(0.12, self._tick)

    def _tick(self) -> None:
        app = self.app
        app._tick += 1
        status = app._cur_status
        if app._spinning and app._track_start:
            status = f"{status}  ({int(time.monotonic() - app._track_start)}s)"
        total = len(app._queue)
        self.query_one("#cassette", Static).update(
            _cassette(app._cur_name, app._cur_artist, app._cur_album,
                      app._q_index, total, status, app._tick, app._spinning)
        )
        # Queue: current + upcoming (current marked ▶)
        qlines = []
        for i in range(app._q_index, total):
            t = app._queue[i]
            prefix = "▶ " if (i == app._q_index and app._spinning) else "  "
            qlines.append(f"{prefix}{t.artist} — {t.name}")
        self.query_one("#queue-text", Static).update("\n".join(qlines) or "  (nothing queued)")
        self.query_one("#queue-title", Static).update(f"Queue  ({total - app._q_index} remaining)")
        # Done
        dlines = [f"{'✓' if ok else '✗'}  {t.name}" for t, ok in app._done]
        self.query_one("#done-text", Static).update("\n".join(dlines) or "  (none yet)")

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()

    def action_quit_app(self) -> None:
        self.app.exit()
