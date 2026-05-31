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

_BOX = 74
_W = 30  # label window inner width

# Rotating reel spokes — 5 wide, 5 tall, narrow glyphs only (no wide unicode)
_SPOKES = [
    ["  │  ", "  │  ", "──+──", "  │  ", "  │  "],
    ["╲   ╱", " ╲ ╱ ", "  +  ", " ╱ ╲ ", "╱   ╲"],
    ["─────", "     ", "──+──", "     ", "─────"],
    ["╱   ╲", " ╱ ╲ ", "  +  ", " ╲ ╱ ", "╲   ╱"],
]


def _fit(s: str, w: int) -> str:
    return (s[:w - 1] + "…") if len(s) > w else s.ljust(w)


def _center(s: str, w: int) -> str:
    s = s[:w]
    pad = w - len(s)
    left = pad // 2
    return " " * left + s + " " * (pad - left)


def _reel(frame: int) -> list[str]:
    sp = _SPOKES[frame]
    return ["╭─────────╮", "│ ╭─────╮ │"] + [f"│ │{r}│ │" for r in sp] + ["│ ╰─────╯ │", "╰─────────╯"]


def _cassette(name, artist, album, done, total, status, tick, spinning) -> str:
    frame = tick % 4 if spinning else 0
    lr = _reel(frame)
    rr = _reel((frame + 2) % 4)
    n, a, b = _fit(name, _W), _fit(artist, _W), _fit(album, _W)
    BAR = 40
    filled = int(done / max(total, 1) * BAR)
    bar = "▓" * filled + "░" * (BAR - filled)
    pct = f"{int(done / max(total, 1) * 100)}%".rjust(4)
    ti = f"track {done} of {total}"

    def row(c: str) -> str:
        return f"  ║{c[:_BOX].ljust(_BOX)}║"

    label = [
        "┌" + "─" * (_W + 2) + "┐",
        "│ " + " " * _W + " │",
        "│ " + n + " │",
        "│ " + " " * _W + " │",
        "│ " + a + " │",
        "│ " + " " * _W + " │",
        "│ " + b + " │",
        "│ " + " " * _W + " │",
        "└" + "─" * (_W + 2) + "┘",
    ]
    lines = [
        "  ╔" + "═" * _BOX + "╗",
        row(""),
        row(_center("C A S S E T T I F Y   ·   SIDE A", _BOX)),
        row(""),
    ]
    for i in range(9):
        lines.append(row("  " + lr[i] + "   " + label[i] + "   " + rr[i]))
    lines += [
        row(""),
        row("  " + ti + "   " + bar + "   " + pct),
        row("  " + _fit(status or "", _BOX - 4)),
        row(""),
        "  ╚" + "═" * _BOX + "╝",
    ]
    return "\n".join(lines)


# ── Download screen (stateless view over app download state) ──────────────────

class DownloadScreen(Screen):

    CSS = """
    #cassette {
        height: 20;
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
        yield Footer()

    def on_mount(self) -> None:
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
