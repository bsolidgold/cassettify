from __future__ import annotations
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Input, Static, Footer, Header, LoadingIndicator
from textual.containers import Center
from textual import on, work
from cassettify.spotify import Playlist, Track, get_tracks_for_source
import spotipy


class TrackScreen(Screen):
    """Drill-in screen for selecting individual tracks from a source."""

    BINDINGS = [
        ("space", "toggle_track", "Select/Deselect"),
        ("a", "select_all", "Select All"),
        ("n", "select_none", "Select None"),
        ("escape", "confirm", "Done"),
    ]

    CSS = """
    TrackScreen { layers: base loader; }
    #loader {
        layer: loader;
        width: 100%;
        height: 100%;
        align: center middle;
        display: none;
    }
    #loader.visible { display: block; }
    #track-table { margin: 0 2; }
    #track-status { dock: bottom; height: 1; margin: 0 2; color: $text-muted; }
    """

    def __init__(self, source: Playlist, sp: spotipy.Spotify) -> None:
        super().__init__()
        self._source = source
        self._sp = sp
        self._tracks: list[Track] = []
        self._selected: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield DataTable(id="track-table", cursor_type="row")
        yield Static("", id="track-status")
        yield Center(LoadingIndicator(), id="loader")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#track-table", DataTable)
        table.add_columns("", "Track", "Artist", "Album")
        self.query_one("#loader").add_class("visible")
        self._load_tracks()

    @work(thread=True)
    def _load_tracks(self) -> None:
        tracks = get_tracks_for_source(self._sp, self._source)
        self.call_from_thread(self._on_tracks_loaded, tracks)

    def _on_tracks_loaded(self, tracks: list[Track]) -> None:
        self._tracks = tracks
        # Pre-select all by default
        self._selected = {t.id for t in tracks}
        self.query_one("#loader").remove_class("visible")
        self._refresh_table()
        self.query_one("#track-table", DataTable).focus()

    def _refresh_table(self) -> None:
        table = self.query_one("#track-table", DataTable)
        table.clear()
        for t in self._tracks:
            check = "✓" if t.id in self._selected else " "
            table.add_row(check, t.name, t.artist, t.album, key=t.id)
        n = len(self._selected)
        total = len(self._tracks)
        self.query_one("#track-status", Static).update(
            f"{n}/{total} selected  ·  Space toggle  ·  A all  ·  N none  ·  Esc done"
        )

    def action_toggle_track(self) -> None:
        table = self.query_one("#track-table", DataTable)
        row = table.cursor_row
        if row is None or row >= len(self._tracks):
            return
        track_id = self._tracks[row].id
        if track_id in self._selected:
            self._selected.discard(track_id)
        else:
            self._selected.add(track_id)
        self._refresh_table()
        table.move_cursor(row=row)

    def action_select_all(self) -> None:
        self._selected = {t.id for t in self._tracks}
        self._refresh_table()

    def action_select_none(self) -> None:
        self._selected.clear()
        self._refresh_table()

    def action_confirm(self) -> None:
        selected = [t for t in self._tracks if t.id in self._selected]
        self.dismiss(selected)


class SourceScreen(Screen):
    """Top-level source picker: Liked Songs, Albums, Playlists."""

    BINDINGS = [
        ("space", "toggle_source", "Select All"),
        ("d", "download", "Download"),
        ("slash", "focus_search", "Search"),
        ("escape", "quit_app", "Quit"),
    ]

    CSS = """
    #search { dock: top; margin: 1 2; display: none; }
    #search.visible { display: block; }
    #source-table { margin: 0 2; }
    #source-status { dock: bottom; height: 1; margin: 0 2; color: $text-muted; }
    """

    def __init__(self, sources: list[Playlist], sp: spotipy.Spotify) -> None:
        super().__init__()
        self._all = sources
        self._filtered = list(sources)
        self._sp = sp
        # None = select all tracks; list[Track] = specific tracks
        self._selection: dict[str, list[Track] | None] = {}
        # Cache of fetched tracks per source
        self._track_cache: dict[str, list[Track]] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Input(placeholder="Search (Esc to close)...", id="search")
        yield DataTable(id="source-table", cursor_type="row")
        yield Static("", id="source-status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#source-table", DataTable)
        table.add_columns("", "Source", "Tracks", "Selected")
        self._refresh_table()
        table.focus()

    def _refresh_table(self) -> None:
        table = self.query_one("#source-table", DataTable)
        table.clear()
        for s in self._filtered:
            if s.id not in self._selection:
                check, sel_label = " ", ""
            else:
                picked = self._selection[s.id]
                check = "✓"
                if picked is None:
                    sel_label = "all"
                else:
                    sel_label = f"{len(picked)} tracks"
            table.add_row(check, s.name, str(s.track_count), sel_label, key=s.id)

        total_tracks = sum(
            len(v) if v is not None else
            (len(self._track_cache[sid]) if sid in self._track_cache else 0)
            for sid, v in self._selection.items()
        )
        n_sources = len(self._selection)
        self.query_one("#source-status", Static).update(
            f"{n_sources} source{'s' if n_sources != 1 else ''} selected  ·  "
            "Space=select all  ·  Enter=browse tracks  ·  D=download  ·  /=search"
        )

    def action_toggle_source(self) -> None:
        table = self.query_one("#source-table", DataTable)
        row = table.cursor_row
        if row is None or row >= len(self._filtered):
            return
        source = self._filtered[row]
        if source.id in self._selection:
            del self._selection[source.id]
        else:
            self._selection[source.id] = None  # select all
        self._refresh_table()
        table.move_cursor(row=row)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#source-table", DataTable)
        row = table.cursor_row
        if row is None or row >= len(self._filtered):
            return
        source = self._filtered[row]

        def handle_result(selected_tracks: list[Track]) -> None:
            if selected_tracks:
                self._track_cache[source.id] = selected_tracks
                self._selection[source.id] = selected_tracks
            elif source.id in self._selection:
                del self._selection[source.id]
            self._refresh_table()
            table.focus()

        self.app.push_screen(TrackScreen(source, self._sp), handle_result)

    def action_download(self) -> None:
        needs_fetch = [
            sid for sid, v in self._selection.items()
            if v is None and sid not in self._track_cache
        ]
        if needs_fetch:
            self.query_one("#source-status", Static).update(
                "Fetching tracks... please wait"
            )
            self._fetch_and_exit(needs_fetch)
        else:
            self.app.exit(self._build_track_list())

    @work(thread=True)
    def _fetch_and_exit(self, source_ids: list[str]) -> None:
        source_map = {s.id: s for s in self._all}
        for sid in source_ids:
            if sid in source_map:
                self._track_cache[sid] = get_tracks_for_source(self._sp, source_map[sid])
        self.call_from_thread(lambda: self.app.exit(self._build_track_list()))

    def _build_track_list(self) -> list[Track]:
        tracks = []
        seen: set[str] = set()
        for source_id, picked in self._selection.items():
            if picked is None:
                # "select all" — use cache if available, else signal to fetch later
                source_tracks = self._track_cache.get(source_id, [])
            else:
                source_tracks = picked
            for t in source_tracks:
                if t.id not in seen:
                    seen.add(t.id)
                    tracks.append(t)
        return tracks

    def action_focus_search(self) -> None:
        search = self.query_one("#search", Input)
        search.add_class("visible")
        search.focus()

    @on(Input.Changed, "#search")
    def filter_sources(self, event: Input.Changed) -> None:
        q = event.value.lower()
        self._filtered = [s for s in self._all if q in s.name.lower()]
        self._refresh_table()

    @on(Input.Submitted, "#search")
    def close_search(self) -> None:
        self.query_one("#search", Input).remove_class("visible")
        self.query_one("#source-table", DataTable).focus()

    def on_key(self, event) -> None:
        if event.key == "escape":
            search = self.query_one("#search", Input)
            if "visible" in search.classes:
                search.set_value("")
                search.remove_class("visible")
                self._filtered = list(self._all)
                self._refresh_table()
                self.query_one("#source-table", DataTable).focus()
                event.stop()

    def action_quit_app(self) -> None:
        self.app.exit(None)


class PickerApp(App):
    """Two-level picker: sources → tracks. Returns list[Track]."""

    TITLE = "cassettify"

    def __init__(self, sources: list[Playlist], sp: spotipy.Spotify) -> None:
        super().__init__()
        self._sources = sources
        self._sp = sp

    def on_mount(self) -> None:
        self.push_screen(SourceScreen(self._sources, self._sp))
