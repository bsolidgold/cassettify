from __future__ import annotations
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Input, Static, Footer, Header
from textual.containers import Vertical
from textual import on
from cassettify.spotify import Playlist


class PickerApp(App):
    """Interactive playlist picker. Returns list of selected Playlist objects."""

    BINDINGS = [
        ("space", "toggle_selection", "Select"),
        ("enter", "confirm", "Download"),
        ("escape", "quit_app", "Quit"),
    ]

    CSS = """
    #search { dock: top; margin: 1 2; }
    #status { dock: bottom; height: 1; margin: 0 2; color: $text-muted; }
    DataTable { margin: 0 2; }
    """

    def __init__(self, playlists: list[Playlist]) -> None:
        super().__init__()
        self._all = playlists
        self._filtered = list(playlists)
        self._selected: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Input(placeholder="Search playlists...", id="search")
        yield DataTable(id="table", cursor_type="row")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("", "Playlist", "Tracks")
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for p in self._filtered:
            check = "✓" if p.id in self._selected else " "
            table.add_row(check, p.name, str(p.track_count), key=p.id)
        n = len(self._selected)
        self.query_one("#status", Static).update(
            f"{n} playlist{'s' if n != 1 else ''} selected  ·  "
            "Space to toggle  ·  Enter to download  ·  Esc to quit"
        )

    @on(Input.Changed, "#search")
    def filter_playlists(self, event: Input.Changed) -> None:
        q = event.value.lower()
        self._filtered = [p for p in self._all if q in p.name.lower()]
        self._refresh_table()

    def action_toggle_selection(self) -> None:
        table = self.query_one(DataTable)
        row_index = table.cursor_row
        if row_index is None or row_index >= len(self._filtered):
            return
        playlist_id = self._filtered[row_index].id
        if playlist_id in self._selected:
            self._selected.discard(playlist_id)
        else:
            self._selected.add(playlist_id)
        self._refresh_table()
        table.move_cursor(row=row_index)

    def action_confirm(self) -> None:
        selected = [p for p in self._all if p.id in self._selected]
        self.exit(selected if selected else None)

    def action_quit_app(self) -> None:
        self.exit(None)
