from __future__ import annotations
import time
from pathlib import Path
from dataclasses import dataclass
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Input, Static, Footer, Header, LoadingIndicator
from textual.containers import Center
from textual.coordinate import Coordinate
from textual import on, work
from cassettify.spotify import (
    Playlist, Track, Artist,
    LIKED_SONGS_ID, get_tracks_for_source,
    get_playlists, get_followed_artists, get_artist_albums,
)
from cassettify import cache
from cassettify import session
from cassettify.downloader import download_track as _dl
from cassettify.ui.progress import DownloadScreen, _interpret
import spotipy

# ── Shared CSS ────────────────────────────────────────────────────────────────

def _short(p: str) -> str:
    home = str(Path.home())
    return "~" + p[len(home):] if p.startswith(home) else p


def _dedupe_by_id(items: list) -> list:
    """Drop items with a duplicate `.id`, preserving order. DataTable row keys
    must be unique, and Spotify sources can contain the same track/album twice."""
    seen: set[str] = set()
    out = []
    for it in items:
        if it.id in seen:
            continue
        seen.add(it.id)
        out.append(it)
    return out


_CSS = """
Screen #bg { dock: top; height: 1; color: $warning; padding: 0 2; }
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
        self._tracks = _dedupe_by_id(tracks)
        ids = {t.id for t in self._tracks}
        if self._select_all:
            self._selected = set(ids)
        else:
            # Restore any previously-picked tracks that still exist in this source
            self._selected = self._preselected & ids
        self.query_one("#loader").remove_class("visible")
        self._refresh()
        self.query_one("#main-table", DataTable).focus()

    def _refresh(self) -> None:
        # Full rebuild — only used on initial load (resets scroll, so avoid on toggles)
        table = self.query_one("#main-table", DataTable)
        table.clear()
        for t in self._tracks:
            table.add_row("✓" if t.id in self._selected else " ", t.name, t.artist, t.album, key=t.id)
        self._update_status()

    def _update_status(self) -> None:
        n, total = len(self._selected), len(self._tracks)
        self.query_one("#status", Static).update(
            f"{n}/{total} selected  ·  Space toggle  ·  A all  ·  N none  ·  Esc done"
            f"   ·   ⤓ {_short(self.app._output_dir)}"
        )

    def _set_check(self, row: int, tid: str) -> None:
        mark = "✓" if tid in self._selected else " "
        self.query_one("#main-table", DataTable).update_cell_at(Coordinate(row, 0), mark)

    def _toggle_row(self, row: int) -> None:
        if row is None or row >= len(self._tracks):
            return
        tid = self._tracks[row].id
        self._selected.discard(tid) if tid in self._selected else self._selected.add(tid)
        self._set_check(row, tid)  # in-place — preserves scroll position
        self._update_status()

    def action_toggle_track(self) -> None:
        self._toggle_row(self.query_one("#main-table", DataTable).cursor_row)

    def action_select_all(self) -> None:
        self._selected = {t.id for t in self._tracks}
        for i, t in enumerate(self._tracks):
            self._set_check(i, t.id)
        self._update_status()

    def action_select_none(self) -> None:
        self._selected.clear()
        for i, t in enumerate(self._tracks):
            self._set_check(i, t.id)
        self._update_status()

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
        yield Static("", id="bg")
        yield Input(placeholder="Search (Esc to close)...", id="search")
        yield DataTable(id="main-table", cursor_type="row")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._setup_columns(self.query_one("#main-table", DataTable))
        self._load_items()
        self.set_interval(0.5, self._refresh_bg)

    def _refresh_bg(self) -> None:
        try:
            self.query_one("#bg", Static).update(self.app.bg_status())
        except Exception:
            pass

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
        self._all_items = _dedupe_by_id(items)
        self._filtered = list(self._all_items)
        for it in self._all_items:
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
            f"   ·   ⤓ {_short(self.app._output_dir)}"
        )

    def action_toggle_item(self) -> None:
        table = self.query_one("#main-table", DataTable)
        row = table.cursor_row
        if row is None or row >= len(self._filtered):
            return
        source = self._filtered[row]
        if source.id in self.app._selection:
            del self.app._selection[source.id]
        else:
            self.app._selection[source.id] = None
        # Update just this row's check + label cells — preserves scroll position
        check, _, _, label = self._row_values(source)
        table.update_cell_at(Coordinate(row, 0), check)
        table.update_cell_at(Coordinate(row, 3), label)
        self._update_status()

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
        yield Static("", id="bg")
        yield DataTable(id="main-table", cursor_type="row")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#main-table", DataTable)
        table.add_columns("Category", "Description")
        for cat in _CATEGORIES:
            table.add_row(cat.name, cat.description, key=cat.id)
        table.focus()
        self.query_one("#status", Static).update(
            "↑↓ navigate  ·  Enter drill in  ·  D download  ·  Esc quit"
            f"   ·   ⤓ {_short(self.app._output_dir)}"
        )
        self.set_interval(0.5, self._refresh_bg)

    def _refresh_bg(self) -> None:
        try:
            self.query_one("#bg", Static).update(self.app.bg_status())
        except Exception:
            pass

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
        self._all_items = _dedupe_by_id(items)
        self._filtered = list(self._all_items)
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
            f"   ·   ⤓ {_short(self.app._output_dir)}"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.query_one("#main-table", DataTable).cursor_row
        if row is None or row >= len(self._filtered):
            return
        self.app.push_screen(ArtistAlbumsScreen(self._filtered[row], self._sp))


# ── App ───────────────────────────────────────────────────────────────────────

class CassettifyApp(App):
    """Unified app: browse library, queue tracks, download in the background."""

    TITLE = "cassettify"
    BINDINGS = [("d", "download", "Download")]

    def __init__(
        self,
        sp: spotipy.Spotify,
        output_dir: str,
        initial_tracks: list[Track] | None = None,
    ) -> None:
        super().__init__()
        self._sp = sp
        self._output_dir = output_dir
        self._initial_tracks = initial_tracks or []
        # Picker state
        self._selection: dict[str, list[Track] | None] = {}
        self._source_registry: dict[str, Playlist] = {}
        # Download state (read by DownloadScreen + bg status bars)
        self._queue: list[Track] = []
        self._queued_ids: set[str] = set()
        self._q_index = 0
        self._done: list[tuple[Track, bool]] = []
        self._cur_name = ""
        self._cur_artist = ""
        self._cur_album = ""
        self._cur_status = ""
        self._spinning = False
        self._tick = 0
        self._track_start = 0.0
        self._worker_started = False
        self._closing = False
        self._cur_proc = None
        self._session_cleared = False

    def on_mount(self) -> None:
        self.push_screen(CategoryScreen())
        # Clean up any partial files from a previous interrupted run, then resume
        # whatever was still queued (plus anything passed in via --all / a name).
        session.cleanup_partials(self._output_dir)
        resume = session.load_pending()
        start = self._initial_tracks + resume
        if start:
            self._enqueue_tracks(start)
            self._ensure_worker()
            self.push_screen(DownloadScreen())

    def on_unmount(self) -> None:
        self._closing = True
        if self._cur_proc is not None:
            try:
                self._cur_proc.terminate()
            except Exception:
                pass

    # ── Selection callbacks ──────────────────────────────────────────────────

    def _handle_liked(self, tracks: list[Track]) -> None:
        if tracks:
            self._selection[LIKED_SONGS_ID] = tracks
        elif LIKED_SONGS_ID in self._selection:
            del self._selection[LIKED_SONGS_ID]

    # ── Download orchestration ────────────────────────────────────────────────

    def action_download(self) -> None:
        if self._selection:
            self._enqueue_selection()
        if not isinstance(self.screen, DownloadScreen):
            if self._queue or self._selection:
                self.push_screen(DownloadScreen())

    def _enqueue_tracks(self, tracks: list[Track]) -> None:
        for t in tracks:
            if t.id in self._queued_ids or cache.contains(t.id):
                continue
            self._queued_ids.add(t.id)
            self._queue.append(t)
        session.save_pending(self._queue[self._q_index:])
        self._session_cleared = False

    @work(thread=True, group="enqueue")
    def _enqueue_selection(self) -> None:
        new_tracks: list[Track] = []
        for sid, picked in list(self._selection.items()):
            if picked is None:
                src = self._source_registry.get(sid)
                tracks = get_tracks_for_source(self._sp, src) if src else []
            else:
                tracks = picked
            new_tracks.extend(tracks)
        self._selection.clear()
        self._enqueue_tracks(new_tracks)
        self._ensure_worker()

    def _ensure_worker(self) -> None:
        if not self._worker_started:
            self._worker_started = True
            self._download_worker()

    @work(thread=True, group="download")
    def _download_worker(self) -> None:
        while not self._closing:
            if self._q_index < len(self._queue):
                track = self._queue[self._q_index]
                self._cur_name = track.name
                self._cur_artist = track.artist
                self._cur_album = track.album
                self._cur_status = "Searching…"
                self._spinning = True
                self._track_start = time.monotonic()

                def on_status(line: str) -> None:
                    phase = _interpret(line)
                    if phase:
                        self._cur_status = phase

                def on_proc(proc) -> None:
                    self._cur_proc = proc

                ok = _dl(track, self._output_dir, on_status, on_proc)
                self._cur_proc = None
                if ok:
                    cache.add(track.id)
                self._done.append((track, ok))
                self._q_index += 1
                # Persist what's left so an interrupted run resumes from here
                session.save_pending(self._queue[self._q_index:])
            else:
                if self._spinning or not self._session_cleared:
                    session.clear()
                    self._session_cleared = True
                self._spinning = False
                if self._q_index > 0:
                    self._cur_name = "All caught up!"
                    self._cur_artist = f"{self._q_index} downloaded"
                    self._cur_album = ""
                    self._cur_status = "Esc to browse · D to add more · Q to quit"
                time.sleep(0.3)

    def bg_status(self) -> str:
        if not self._worker_started:
            return ""
        total = len(self._queue)
        if self._q_index >= total and not self._spinning:
            return f"✓ Downloads complete — {self._q_index} track(s)"
        return f"▶ Downloading {min(self._q_index + 1, total)}/{total} · {self._cur_name}   (press D to view)"
