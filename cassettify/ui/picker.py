from __future__ import annotations
from dataclasses import dataclass
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Input, Static, Footer, Header, LoadingIndicator
from textual.containers import Center
from textual import on, work
from cassettify.spotify import (
    Playlist, Track, Artist,
    LIKED_SONGS_ID, get_tracks_for_source,
    get_playlists, get_followed_artists, get_artist_albums,
)
import spotipy

# ── Shared CSS ────────────────────────────────────────────────────────────────

_CSS = """
Screen #search { dock: top; margin: 1 2; display: none; }
Screen #search.visible { display: block; }
Screen #main-table { margin: 0 2; }
Screen #status { dock: bottom; height: 1; margin: 0 2; color: $text-muted; }
Screen #loader { width: 100%; height: 1fr; align: center middle; display: none; }
Screen #loader.visible { display: block; }
"""

# ── Track picker (leaf screen) ────────────────────────────────────────────────

class TrackScreen(Screen):
    """Select individual tracks from a source. Dismisses with list[Track]."""

    CSS = _CSS + """
    TrackScreen { layers: base loader; }
    #loader { layer: loader; }
    """

    BINDINGS = [
        ("space", "toggle_track", "Select/Deselect"),
        ("a", "select_all", "Select All"),
        ("n", "select_none", "Select None"),
        ("d", "commit_and_download", "Download"),
        ("escape", "confirm", "Done"),
    ]

    def __init__(
        self,
        source: Playlist,
        sp: spotipy.Spotify,
        preselected: set[str] | None = None,
        select_all: bool = False,
    ) -> None:
        super().__init__()
        self._source = source
        self._sp = sp
        self._preselected = preselected or set()
        self._select_all = select_all
        self._tracks: list[Track] = []
        self._selected: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield DataTable(id="main-table", cursor_type="row")
        yield Static("", id="status")
        yield Center(LoadingIndicator(), id="loader")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#main-table", DataTable).add_columns("", "Track", "Artist", "Album")
        self.query_one("#loader").add_class("visible")
        self._load_tracks()

    @work(thread=True)
    def _load_tracks(self) -> None:
        tracks = get_tracks_for_source(self._sp, self._source)
        self.app.call_from_thread(self._on_loaded, tracks)

    def _on_loaded(self, tracks: list[Track]) -> None:
        self._tracks = tracks
        ids = {t.id for t in tracks}
        if self._select_all:
            self._selected = set(ids)
        else:
            # Restore any previously-picked tracks that still exist in this source
            self._selected = self._preselected & ids
        self.query_one("#loader").remove_class("visible")
        self._refresh()
        self.query_one("#main-table", DataTable).focus()

    def _refresh(self) -> None:
        table = self.query_one("#main-table", DataTable)
        table.clear()
        for t in self._tracks:
            table.add_row("✓" if t.id in self._selected else " ", t.name, t.artist, t.album, key=t.id)
        n, total = len(self._selected), len(self._tracks)
        self.query_one("#status", Static).update(
            f"{n}/{total} selected  ·  Space toggle  ·  A all  ·  N none  ·  Esc done"
        )

    def _toggle_row(self, row: int) -> None:
        if row is None or row >= len(self._tracks):
            return
        tid = self._tracks[row].id
        self._selected.discard(tid) if tid in self._selected else self._selected.add(tid)
        self._refresh()
        self.query_one("#main-table", DataTable).move_cursor(row=row)

    def action_toggle_track(self) -> None:
        self._toggle_row(self.query_one("#main-table", DataTable).cursor_row)

    def action_select_all(self) -> None:
        self._selected = {t.id for t in self._tracks}
        self._refresh()

    def action_select_none(self) -> None:
        self._selected.clear()
        self._refresh()

    def action_confirm(self) -> None:
        self.dismiss([t for t in self._tracks if t.id in self._selected])

    def action_commit_and_download(self) -> None:
        # Commit this screen's current selection, then trigger a download
        selected = [t for t in self._tracks if t.id in self._selected]
        if selected:
            self.app._selection[self._source.id] = selected
        elif self._source.id in self.app._selection:
            del self.app._selection[self._source.id]
        self.app.action_download()


# ── Generic lazy-loading list screen ─────────────────────────────────────────

class _ListScreen(Screen):
    """Base for screens that load a list and support search."""

    CSS = _CSS

    BINDINGS = [
        ("space", "toggle_item", "Select All"),
        ("slash", "focus_search", "Search"),
        ("escape", "go_back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._all_items: list = []
        self._filtered: list = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Input(placeholder="Search (Esc to close)...", id="search")
        yield DataTable(id="main-table", cursor_type="row")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._setup_columns(self.query_one("#main-table", DataTable))
        self._load_items()

    def on_screen_resume(self) -> None:
        # Reflect any selection changes made elsewhere (e.g. after a download commit)
        if self._all_items:
            self._refresh()

    def _setup_columns(self, table: DataTable) -> None:
        raise NotImplementedError

    def _load_items(self) -> None:
        raise NotImplementedError

    def _row_values(self, item) -> tuple:
        raise NotImplementedError

    def _item_key(self, item) -> str:
        raise NotImplementedError

    def _refresh(self) -> None:
        table = self.query_one("#main-table", DataTable)
        row = table.cursor_row
        table.clear()
        for item in self._filtered:
            table.add_row(*self._row_values(item), key=self._item_key(item))
        if row is not None and self._filtered:
            table.move_cursor(row=min(row, len(self._filtered) - 1))
        self._update_status()

    def _update_status(self) -> None:
        pass

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_toggle_item(self) -> None:
        pass  # override in subclasses that support selection

    def action_focus_search(self) -> None:
        s = self.query_one("#search", Input)
        s.add_class("visible")
        s.focus()

    @on(Input.Changed, "#search")
    def _filter(self, event: Input.Changed) -> None:
        q = event.value.lower()
        self._filtered = [i for i in self._all_items if q in self._search_key(i).lower()]
        self._refresh()

    def _search_key(self, item) -> str:
        return str(item)

    @on(Input.Submitted, "#search")
    def _close_search(self) -> None:
        self.query_one("#search", Input).remove_class("visible")
        self.query_one("#main-table", DataTable).focus()

    def on_key(self, event) -> None:
        if event.key == "escape":
            s = self.query_one("#search", Input)
            if "visible" in s.classes:
                s.set_value("")
                s.remove_class("visible")
                self._filtered = list(self._all_items)
                self._refresh()
                self.query_one("#main-table", DataTable).focus()
                event.stop()


# ── Shared base for selectable source lists (playlists / albums) ──────────────

class _SourceListScreen(_ListScreen):
    """A list of selectable sources. Space = select whole source, Enter = pick tracks."""

    COLUMNS = ("", "Source", "Tracks", "Selected")

    def __init__(self, sp: spotipy.Spotify) -> None:
        super().__init__()
        self._sp = sp

    def _setup_columns(self, table: DataTable) -> None:
        table.add_columns(*self.COLUMNS)

    def _load_items(self) -> None:
        self._load_async()

    @work(thread=True)
    def _load_async(self) -> None:
        items = self._fetch()
        self.app.call_from_thread(self._on_loaded, items)

    def _fetch(self) -> list[Playlist]:
        raise NotImplementedError

    def _on_loaded(self, items: list[Playlist]) -> None:
        self._all_items = items
        self._filtered = list(items)
        for it in items:
            self.app._source_registry[it.id] = it
        self._refresh()
        self.query_one("#main-table", DataTable).focus()

    def _row_values(self, item: Playlist) -> tuple:
        if item.id not in self.app._selection:
            return " ", item.name, str(item.track_count), ""
        sel = self.app._selection[item.id]
        label = "all" if sel is None else f"{len(sel)} tracks"
        return "✓", item.name, str(item.track_count), label

    def _item_key(self, item: Playlist) -> str:
        return item.id

    def _search_key(self, item: Playlist) -> str:
        return item.name

    def _update_status(self) -> None:
        n = sum(1 for s in self._all_items if s.id in self.app._selection)
        self.query_one("#status", Static).update(
            f"{n} selected  ·  Space=select all  ·  Enter=browse  ·  D=download  ·  /=search"
        )

    def action_toggle_item(self) -> None:
        row = self.query_one("#main-table", DataTable).cursor_row
        if row is None or row >= len(self._filtered):
            return
        source = self._filtered[row]
        if source.id in self.app._selection:
            del self.app._selection[source.id]
        else:
            self.app._selection[source.id] = None
        self._refresh()
        self.query_one("#main-table", DataTable).move_cursor(row=row)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#main-table", DataTable)
        row = table.cursor_row
        if row is None or row >= len(self._filtered):
            return
        source = self._filtered[row]

        # Restore prior selection state for this source
        if source.id in self.app._selection:
            val = self.app._selection[source.id]
            if val is None:
                screen = TrackScreen(source, self._sp, select_all=True)
            else:
                screen = TrackScreen(source, self._sp, preselected={t.id for t in val})
        else:
            screen = TrackScreen(source, self._sp)

        def handle(tracks: list[Track]) -> None:
            if tracks:
                self.app._selection[source.id] = tracks
            elif source.id in self.app._selection:
                del self.app._selection[source.id]
            self._refresh()
            table.focus()
            table.move_cursor(row=row)

        self.app.push_screen(screen, handle)


# ── Category screen ───────────────────────────────────────────────────────────

@dataclass
class _Category:
    id: str
    name: str
    description: str


_CATEGORIES = [
    _Category("liked",     "♥  Liked Songs",      "Your saved tracks"),
    _Category("playlists", "◈  Playlists",         "Your Spotify playlists"),
    _Category("albums",    "▣  Saved Albums",      "Albums you've saved"),
    _Category("artists",   "♪  Followed Artists",  "Artists you follow"),
]


class CategoryScreen(Screen):
    """Top-level category picker."""

    CSS = _CSS
    BINDINGS = [("escape", "quit_app", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield DataTable(id="main-table", cursor_type="row")
        yield Static("↑↓ navigate  ·  Enter drill in  ·  D download  ·  Esc quit", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#main-table", DataTable)
        table.add_columns("Category", "Description")
        for cat in _CATEGORIES:
            table.add_row(cat.name, cat.description, key=cat.id)
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.query_one("#main-table", DataTable).cursor_row
        if row is None:
            return
        cat = _CATEGORIES[row]
        sp = self.app._sp
        if cat.id == "liked":
            liked = Playlist(
                id=LIKED_SONGS_ID, name="♥  Liked Songs",
                track_count=0, cover_url=None, source_type="liked",
            )
            prior = self.app._selection.get(LIKED_SONGS_ID)
            pre = {t.id for t in prior} if prior else set()
            self.app.push_screen(TrackScreen(liked, sp, preselected=pre), self.app._handle_liked)
        elif cat.id == "playlists":
            self.app.push_screen(PlaylistsScreen(sp))
        elif cat.id == "albums":
            self.app.push_screen(SavedAlbumsScreen(sp))
        elif cat.id == "artists":
            self.app.push_screen(ArtistsScreen(sp))

    def action_quit_app(self) -> None:
        self.app.exit(None)


# ── Concrete source lists ─────────────────────────────────────────────────────

class PlaylistsScreen(_SourceListScreen):
    COLUMNS = ("", "Playlist", "Tracks", "Selected")

    def _fetch(self) -> list[Playlist]:
        return get_playlists(self._sp)


class SavedAlbumsScreen(_SourceListScreen):
    COLUMNS = ("", "Album", "Tracks", "Selected")

    def _fetch(self) -> list[Playlist]:
        results = self._sp.current_user_saved_albums(limit=50)
        albums = []
        while results:
            for item in results["items"]:
                a = item["album"]
                cover = a["images"][0]["url"] if a["images"] else None
                albums.append(Playlist(
                    id=a["id"], name=a["name"],
                    track_count=a["total_tracks"], cover_url=cover, source_type="album",
                ))
            results = self._sp.next(results) if results["next"] else None
        return albums


class ArtistAlbumsScreen(_SourceListScreen):
    COLUMNS = ("", "Album", "Tracks", "Selected")

    def __init__(self, artist: Artist, sp: spotipy.Spotify) -> None:
        super().__init__(sp)
        self._artist = artist

    def _fetch(self) -> list[Playlist]:
        return get_artist_albums(self._sp, self._artist.id)


# ── Artists screen (navigation only, not selectable) ──────────────────────────

class ArtistsScreen(_ListScreen):

    def __init__(self, sp: spotipy.Spotify) -> None:
        super().__init__()
        self._sp = sp

    def _setup_columns(self, table: DataTable) -> None:
        table.add_columns("Artist")

    def _load_items(self) -> None:
        self._load_async()

    @work(thread=True)
    def _load_async(self) -> None:
        artists = get_followed_artists(self._sp)
        self.app.call_from_thread(self._on_loaded, artists)

    def _on_loaded(self, items: list[Artist]) -> None:
        self._all_items = items
        self._filtered = list(items)
        self._refresh()
        self.query_one("#main-table", DataTable).focus()

    def _row_values(self, item: Artist) -> tuple:
        return (item.name,)

    def _item_key(self, item: Artist) -> str:
        return item.id

    def _search_key(self, item: Artist) -> str:
        return item.name

    def _update_status(self) -> None:
        self.query_one("#status", Static).update(
            "Enter=browse albums  ·  D=download  ·  /=search  ·  Esc=back"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.query_one("#main-table", DataTable).cursor_row
        if row is None or row >= len(self._filtered):
            return
        self.app.push_screen(ArtistAlbumsScreen(self._filtered[row], self._sp))


# ── App ───────────────────────────────────────────────────────────────────────

class PickerApp(App):
    """Multi-level picker. Returns list[Track]."""

    TITLE = "cassettify"
    BINDINGS = [("d", "download", "Download")]

    def __init__(self, sp: spotipy.Spotify) -> None:
        super().__init__()
        self._sp = sp
        self._selection: dict[str, list[Track] | None] = {}
        self._source_registry: dict[str, Playlist] = {}

    def on_mount(self) -> None:
        self.push_screen(CategoryScreen())

    def _handle_liked(self, tracks: list[Track]) -> None:
        if tracks:
            self._selection[LIKED_SONGS_ID] = tracks
        elif LIKED_SONGS_ID in self._selection:
            del self._selection[LIKED_SONGS_ID]

    def action_download(self) -> None:
        if not self._selection:
            return
        needs_fetch = [
            sid for sid, v in self._selection.items()
            if v is None
        ]
        if needs_fetch:
            self._fetch_and_exit(needs_fetch)
        else:
            self.exit(self._build_tracks())

    @work(thread=True)
    def _fetch_and_exit(self, source_ids: list[str]) -> None:
        for sid in source_ids:
            source = self._source_registry.get(sid)
            if source:
                self._selection[sid] = get_tracks_for_source(self._sp, source)
        self.call_from_thread(lambda: self.exit(self._build_tracks()))

    def _build_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        seen: set[str] = set()
        for picked in self._selection.values():
            for t in (picked or []):
                if t.id not in seen:
                    seen.add(t.id)
                    tracks.append(t)
        return tracks
