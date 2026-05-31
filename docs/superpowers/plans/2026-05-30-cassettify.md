# Cassettify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that connects to Spotify, lets the user pick playlists via an interactive Textual TUI, and downloads them as tagged MP3s organized by Artist/Album.

**Architecture:** Thin wrapper around `spotdl` for downloading. `spotipy` handles Spotify auth and playlist metadata. `textual` provides the interactive TUI — wizard, picker, and progress screens. `cli.py` wires everything together via `typer`.

**Tech Stack:** Python 3.11+, spotipy, spotdl, textual, rich, typer, requests, pytest

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, dependencies, entry point |
| `cassettify/__init__.py` | Empty package marker |
| `cassettify/config.py` | Read/write `~/.cassettify/config.json` |
| `cassettify/cache.py` | Track downloaded-ID registry in `~/.cassettify/cache.json` |
| `cassettify/auth.py` | Spotify OAuth client factory via spotipy |
| `cassettify/spotify.py` | Fetch playlists and tracks from Spotify API |
| `cassettify/downloader.py` | spotdl subprocess wrapper, failure logging |
| `cassettify/ui/__init__.py` | Empty package marker |
| `cassettify/ui/wizard.py` | Textual first-run setup wizard |
| `cassettify/ui/picker.py` | Textual playlist picker (search + multi-select) |
| `cassettify/ui/progress.py` | Textual download progress display |
| `cassettify/ui/app.py` | Orchestrator — runs wizard/picker/progress in sequence |
| `cassettify/cli.py` | typer entry point, argument parsing |
| `tests/test_config.py` | Unit tests for config.py |
| `tests/test_cache.py` | Unit tests for cache.py |
| `tests/test_spotify.py` | Mock tests for spotify.py |
| `Formula/cassettify.rb` | Homebrew formula |

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `cassettify/__init__.py`
- Create: `cassettify/ui/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
cd /Users/bretgold/gitHub/cassettify
mkdir -p cassettify/ui tests Formula
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cassettify"
version = "0.1.0"
description = "Download your Spotify playlists for your iPod Classic"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
    "spotipy>=2.23.0",
    "spotdl>=4.2.0",
    "textual>=0.47.0",
    "rich>=13.7.0",
    "typer>=0.9.0",
    "requests>=2.31.0",
]

[project.scripts]
cassettify = "cassettify.cli:app"

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.21",
]

[tool.hatch.build.targets.wheel]
packages = ["cassettify"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 3: Create empty `__init__.py` files**

```bash
touch cassettify/__init__.py cassettify/ui/__init__.py tests/__init__.py
```

- [ ] **Step 4: Create and activate virtual environment**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Expected: All packages install without errors.

- [ ] **Step 5: Verify entry point is registered**

```bash
cassettify --help
```

Expected: `Error: No such command` or similar — the module doesn't exist yet, but the entry point resolves. (A ModuleNotFoundError for `cassettify.cli` is acceptable at this stage.)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml cassettify/ tests/ Formula/
git commit -m "feat: project scaffold"
```

---

## Task 2: Config Module

**Files:**
- Create: `cassettify/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from cassettify.config import Config


def test_load_returns_none_when_no_file(tmp_path):
    with patch("cassettify.config.CONFIG_FILE", tmp_path / "config.json"), \
         patch("cassettify.config.CONFIG_DIR", tmp_path):
        assert Config.load() is None


def test_save_and_load_roundtrip(tmp_path):
    config_file = tmp_path / "config.json"
    with patch("cassettify.config.CONFIG_FILE", config_file), \
         patch("cassettify.config.CONFIG_DIR", tmp_path):
        cfg = Config(client_id="abc", client_secret="xyz", output_dir="/tmp/music")
        cfg.save()
        loaded = Config.load()
    assert loaded.client_id == "abc"
    assert loaded.client_secret == "xyz"
    assert loaded.output_dir == "/tmp/music"


def test_save_creates_directory(tmp_path):
    config_dir = tmp_path / "cassettify"
    config_file = config_dir / "config.json"
    with patch("cassettify.config.CONFIG_FILE", config_file), \
         patch("cassettify.config.CONFIG_DIR", config_dir):
        cfg = Config(client_id="abc", client_secret="xyz", output_dir="/tmp")
        cfg.save()
    assert config_file.exists()


def test_load_parses_all_fields(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "client_id": "myid",
        "client_secret": "mysecret",
        "output_dir": "/music",
    }))
    with patch("cassettify.config.CONFIG_FILE", config_file), \
         patch("cassettify.config.CONFIG_DIR", tmp_path):
        cfg = Config.load()
    assert cfg.client_id == "myid"
    assert cfg.output_dir == "/music"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'cassettify.config'`

- [ ] **Step 3: Implement `cassettify/config.py`**

```python
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".cassettify"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    client_id: str
    client_secret: str
    output_dir: str

    @classmethod
    def load(cls) -> Optional["Config"]:
        if not CONFIG_FILE.exists():
            return None
        data = json.loads(CONFIG_FILE.read_text())
        return cls(**data)

    def save(self) -> None:
        CONFIG_DIR.mkdir(exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2))
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_config.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add cassettify/config.py tests/test_config.py
git commit -m "feat: config module with save/load"
```

---

## Task 3: Cache Module

**Files:**
- Create: `cassettify/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cache.py`:

```python
import pytest
from unittest.mock import patch
from cassettify import cache


def test_load_returns_empty_set_when_no_file(tmp_path):
    with patch("cassettify.cache.CACHE_FILE", tmp_path / "cache.json"):
        assert cache.load() == set()


def test_add_and_contains(tmp_path):
    cache_file = tmp_path / "cache.json"
    with patch("cassettify.cache.CACHE_FILE", cache_file):
        cache.add("track_123")
        assert cache.contains("track_123")
        assert not cache.contains("track_456")


def test_add_is_idempotent(tmp_path):
    cache_file = tmp_path / "cache.json"
    with patch("cassettify.cache.CACHE_FILE", cache_file):
        cache.add("track_123")
        cache.add("track_123")
        assert len(cache.load()) == 1


def test_add_multiple_tracks(tmp_path):
    cache_file = tmp_path / "cache.json"
    with patch("cassettify.cache.CACHE_FILE", cache_file):
        cache.add("track_a")
        cache.add("track_b")
        cache.add("track_c")
        assert cache.contains("track_a")
        assert cache.contains("track_b")
        assert cache.contains("track_c")
        assert not cache.contains("track_d")


def test_persists_across_calls(tmp_path):
    cache_file = tmp_path / "cache.json"
    with patch("cassettify.cache.CACHE_FILE", cache_file):
        cache.add("track_123")
    # New patch context simulates a fresh process load
    with patch("cassettify.cache.CACHE_FILE", cache_file):
        assert cache.contains("track_123")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_cache.py -v
```

Expected: `ModuleNotFoundError: No module named 'cassettify.cache'`

- [ ] **Step 3: Implement `cassettify/cache.py`**

```python
from __future__ import annotations
import json
from pathlib import Path

CACHE_FILE = Path.home() / ".cassettify" / "cache.json"


def load() -> set[str]:
    if not CACHE_FILE.exists():
        return set()
    return set(json.loads(CACHE_FILE.read_text()))


def add(track_id: str) -> None:
    ids = load()
    ids.add(track_id)
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(sorted(ids), indent=2))


def contains(track_id: str) -> bool:
    return track_id in load()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_cache.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add cassettify/cache.py tests/test_cache.py
git commit -m "feat: cache module for tracking downloaded tracks"
```

---

## Task 4: Auth Module

**Files:**
- Create: `cassettify/auth.py`

No automated tests — this wraps Spotify OAuth which requires browser interaction. Verified end-to-end in Task 11.

- [ ] **Step 1: Implement `cassettify/auth.py`**

```python
from __future__ import annotations
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from cassettify.config import Config, CONFIG_DIR

SCOPE = "playlist-read-private playlist-read-collaborative"
_CACHE_PATH = str(CONFIG_DIR / ".spotify_cache")


def get_client(config: Config) -> spotipy.Spotify:
    auth_manager = SpotifyOAuth(
        client_id=config.client_id,
        client_secret=config.client_secret,
        redirect_uri="http://localhost:8888/callback",
        scope=SCOPE,
        cache_path=_CACHE_PATH,
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth_manager)
```

- [ ] **Step 2: Commit**

```bash
git add cassettify/auth.py
git commit -m "feat: spotify auth module"
```

---

## Task 5: Spotify Module

**Files:**
- Create: `cassettify/spotify.py`
- Create: `tests/test_spotify.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_spotify.py`:

```python
import pytest
from unittest.mock import MagicMock
from cassettify.spotify import (
    get_playlists, get_tracks, find_playlist_by_name, Playlist, Track
)


def _sp_with_playlists(items, next_page=None):
    sp = MagicMock()
    sp.current_user_playlists.return_value = {"items": items, "next": next_page}
    sp.next.return_value = {"items": [], "next": None}
    return sp


def test_get_playlists_basic():
    sp = _sp_with_playlists([
        {"id": "pl1", "name": "My Mix", "tracks": {"total": 10},
         "images": [{"url": "http://art.jpg"}]},
        {"id": "pl2", "name": "Chill", "tracks": {"total": 5}, "images": []},
    ])
    result = get_playlists(sp)
    assert len(result) == 2
    assert result[0].name == "My Mix"
    assert result[0].track_count == 10
    assert result[0].cover_url == "http://art.jpg"
    assert result[1].cover_url is None


def test_get_playlists_paginates():
    sp = MagicMock()
    sp.current_user_playlists.return_value = {
        "items": [{"id": "pl1", "name": "A", "tracks": {"total": 1}, "images": []}],
        "next": "page2",
    }
    sp.next.return_value = {
        "items": [{"id": "pl2", "name": "B", "tracks": {"total": 2}, "images": []}],
        "next": None,
    }
    result = get_playlists(sp)
    assert len(result) == 2
    assert result[1].name == "B"


def _make_track_item(track_id, name, is_local=False):
    return {
        "track": {
            "id": track_id,
            "name": name,
            "is_local": is_local,
            "artists": [{"name": "Test Artist"}],
            "album": {"name": "Test Album", "images": [{"url": "http://art.jpg"}]},
            "external_urls": {"spotify": f"https://open.spotify.com/track/{track_id}"},
        }
    }


def test_get_tracks_returns_tracks():
    sp = MagicMock()
    sp.playlist_tracks.return_value = {
        "items": [_make_track_item("t1", "Song One"), _make_track_item("t2", "Song Two")],
        "next": None,
    }
    result = get_tracks(sp, "pl1")
    assert len(result) == 2
    assert result[0].id == "t1"
    assert result[0].name == "Song One"
    assert result[0].artist == "Test Artist"
    assert result[0].album_art_url == "http://art.jpg"


def test_get_tracks_skips_local_tracks():
    sp = MagicMock()
    sp.playlist_tracks.return_value = {
        "items": [
            _make_track_item("t1", "Normal"),
            _make_track_item("t2", "Local File", is_local=True),
        ],
        "next": None,
    }
    result = get_tracks(sp, "pl1")
    assert len(result) == 1
    assert result[0].name == "Normal"


def test_get_tracks_skips_none_tracks():
    sp = MagicMock()
    sp.playlist_tracks.return_value = {
        "items": [{"track": None}, _make_track_item("t1", "Real")],
        "next": None,
    }
    result = get_tracks(sp, "pl1")
    assert len(result) == 1


def test_find_playlist_by_name_exact():
    playlists = [
        Playlist(id="1", name="Dark Side", track_count=10, cover_url=None),
        Playlist(id="2", name="Wish You Were Here", track_count=9, cover_url=None),
    ]
    assert find_playlist_by_name(playlists, "Dark Side").id == "1"


def test_find_playlist_by_name_case_insensitive():
    playlists = [Playlist(id="1", name="Dark Side", track_count=10, cover_url=None)]
    assert find_playlist_by_name(playlists, "dark side").id == "1"
    assert find_playlist_by_name(playlists, "DARK SIDE").id == "1"


def test_find_playlist_by_name_returns_none_when_not_found():
    playlists = [Playlist(id="1", name="Dark Side", track_count=10, cover_url=None)]
    assert find_playlist_by_name(playlists, "Animals") is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_spotify.py -v
```

Expected: `ModuleNotFoundError: No module named 'cassettify.spotify'`

- [ ] **Step 3: Implement `cassettify/spotify.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import spotipy


@dataclass
class Track:
    id: str
    name: str
    artist: str
    album: str
    album_art_url: Optional[str]
    spotify_url: str


@dataclass
class Playlist:
    id: str
    name: str
    track_count: int
    cover_url: Optional[str]


def get_playlists(sp: spotipy.Spotify) -> list[Playlist]:
    playlists = []
    results = sp.current_user_playlists(limit=50)
    while results:
        for item in results["items"]:
            cover = item["images"][0]["url"] if item["images"] else None
            playlists.append(Playlist(
                id=item["id"],
                name=item["name"],
                track_count=item["tracks"]["total"],
                cover_url=cover,
            ))
        results = sp.next(results) if results["next"] else None
    return playlists


def get_tracks(sp: spotipy.Spotify, playlist_id: str) -> list[Track]:
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    while results:
        for item in results["items"]:
            t = item.get("track")
            if not t or t.get("is_local"):
                continue
            art = t["album"]["images"][0]["url"] if t["album"]["images"] else None
            tracks.append(Track(
                id=t["id"],
                name=t["name"],
                artist=t["artists"][0]["name"],
                album=t["album"]["name"],
                album_art_url=art,
                spotify_url=t["external_urls"]["spotify"],
            ))
        results = sp.next(results) if results["next"] else None
    return tracks


def find_playlist_by_name(
    playlists: list[Playlist], name: str
) -> Optional[Playlist]:
    name_lower = name.lower()
    for p in playlists:
        if p.name.lower() == name_lower:
            return p
    return None
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_spotify.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Run the full test suite to confirm nothing broke**

```bash
pytest -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add cassettify/spotify.py tests/test_spotify.py
git commit -m "feat: spotify module for playlists and tracks"
```

---

## Task 6: Downloader Module

**Files:**
- Create: `cassettify/downloader.py`

No unit tests — this wraps a subprocess. Verified end-to-end in Task 11.

- [ ] **Step 1: Implement `cassettify/downloader.py`**

```python
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from cassettify.spotify import Track

FAILED_LOG = Path.home() / ".cassettify" / "failed.log"

_OUTPUT_TEMPLATE = "{artists}/{album}/{track-number} - {title}.{output-ext}"


def download_track(track: Track, output_dir: str) -> bool:
    """Download a single track via spotdl. Returns True on success."""
    full_template = str(Path(output_dir) / _OUTPUT_TEMPLATE)
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "spotdl",
                track.spotify_url,
                "--output", full_template,
                "--format", "mp3",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            _log_failure(track, result.stderr.strip())
            return False
        return True
    except subprocess.TimeoutExpired:
        _log_failure(track, "timeout after 120s")
        return False
    except Exception as e:
        _log_failure(track, str(e))
        return False


def _log_failure(track: Track, reason: str) -> None:
    FAILED_LOG.parent.mkdir(exist_ok=True)
    with FAILED_LOG.open("a") as f:
        f.write(f"{track.artist} - {track.name} ({track.id}): {reason}\n")
```

- [ ] **Step 2: Commit**

```bash
git add cassettify/downloader.py
git commit -m "feat: downloader module wrapping spotdl"
```

---

## Task 7: Wizard TUI

**Files:**
- Create: `cassettify/ui/wizard.py`

- [ ] **Step 1: Implement `cassettify/ui/wizard.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, Button, Label
from textual.containers import Container
from textual import on


@dataclass
class WizardResult:
    client_id: str
    client_secret: str
    output_dir: str


class WelcomeScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Container(
            Static("[bold]Welcome to Cassettify[/bold]", classes="title"),
            Static(
                "Let's connect your Spotify account.\nThis takes about 2 minutes.",
                classes="subtitle",
            ),
            Button("Let's go →", id="next", variant="primary"),
            classes="card",
        )

    @on(Button.Pressed, "#next")
    def next(self) -> None:
        self.app.push_screen(InstructionsScreen())


class InstructionsScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Container(
            Static("[bold]Step 1: Create a free Spotify app[/bold]\n"),
            Static(
                "1. Go to [link=https://developer.spotify.com/dashboard]"
                "developer.spotify.com/dashboard[/link]\n"
                "2. Log in and click [bold]Create app[/bold]\n"
                "3. Set Redirect URI to: [bold]http://localhost:8888/callback[/bold]\n"
                "4. Copy your [bold]Client ID[/bold] and [bold]Client Secret[/bold]"
            ),
            Button("I've got my credentials →", id="next", variant="primary"),
            classes="card",
        )

    @on(Button.Pressed, "#next")
    def next(self) -> None:
        self.app.push_screen(CredentialsScreen())


class CredentialsScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Container(
            Static("[bold]Paste your Spotify credentials[/bold]\n"),
            Label("Client ID"),
            Input(placeholder="Paste here...", id="client_id"),
            Label("Client Secret"),
            Input(placeholder="Paste here...", password=True, id="client_secret"),
            Static("", id="error", classes="error"),
            Button("Connect →", id="next", variant="primary"),
            classes="card",
        )

    @on(Button.Pressed, "#next")
    def submit(self) -> None:
        client_id = self.query_one("#client_id", Input).value.strip()
        client_secret = self.query_one("#client_secret", Input).value.strip()
        if not client_id or not client_secret:
            self.query_one("#error", Static).update("Both fields are required.")
            return
        self.app.wizard_client_id = client_id
        self.app.wizard_client_secret = client_secret
        self.app.push_screen(OutputDirScreen())


class OutputDirScreen(Screen):
    _default = str(Path.home() / "Music" / "Cassettify")

    def compose(self) -> ComposeResult:
        yield Container(
            Static("[bold]Where should songs be saved?[/bold]\n"),
            Input(value=self._default, id="output_dir"),
            Button("Finish setup →", id="next", variant="primary"),
            classes="card",
        )

    @on(Button.Pressed, "#next")
    def submit(self) -> None:
        output_dir = self.query_one("#output_dir", Input).value.strip() or self._default
        self.app.exit(WizardResult(
            client_id=self.app.wizard_client_id,
            client_secret=self.app.wizard_client_secret,
            output_dir=output_dir,
        ))


class WizardApp(App):
    CSS = """
    Screen { align: center middle; }
    .card {
        width: 64;
        height: auto;
        border: solid $primary;
        padding: 2 4;
    }
    .title { text-style: bold; margin-bottom: 1; }
    .subtitle { color: $text-muted; margin-bottom: 2; }
    .error { color: red; height: 1; margin-top: 1; }
    Button { margin-top: 2; }
    Input { margin-top: 1; margin-bottom: 1; }
    """

    wizard_client_id: str = ""
    wizard_client_secret: str = ""

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())
```

- [ ] **Step 2: Smoke-test the wizard renders**

```bash
python -c "
from cassettify.ui.wizard import WizardApp
print('WizardApp imported OK')
"
```

Expected: `WizardApp imported OK`

- [ ] **Step 3: Commit**

```bash
git add cassettify/ui/wizard.py
git commit -m "feat: first-run wizard TUI"
```

---

## Task 8: Picker TUI

**Files:**
- Create: `cassettify/ui/picker.py`

- [ ] **Step 1: Implement `cassettify/ui/picker.py`**

```python
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
        if row_index >= len(self._filtered):
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
```

- [ ] **Step 2: Smoke-test the picker renders**

```bash
python -c "
from cassettify.ui.picker import PickerApp
from cassettify.spotify import Playlist
p = Playlist(id='1', name='Test', track_count=5, cover_url=None)
app = PickerApp([p])
print('PickerApp imported OK')
"
```

Expected: `PickerApp imported OK`

- [ ] **Step 3: Commit**

```bash
git add cassettify/ui/picker.py
git commit -m "feat: playlist picker TUI"
```

---

## Task 9: Progress TUI

**Files:**
- Create: `cassettify/ui/progress.py`

- [ ] **Step 1: Implement `cassettify/ui/progress.py`**

```python
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
        border: solid $primary-darken-2;
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
            # Remove from queue
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
                done_list.append(ListItem(Label(f"✓ {track.name}", classes="done-label")))
            else:
                done_list.append(ListItem(Label(f"✗ {track.name}", classes="fail-label")))

        total = len(self._tracks)
        self.query_one("#track-name", Static).update(
            f"[bold green]All done![/bold green]  {done_count}/{total} tracks downloaded"
        )
        self.query_one("#artist-album", Static).update("Press Q to quit")

    def action_quit_app(self) -> None:
        self.exit()
```

- [ ] **Step 2: Smoke-test the progress screen renders**

```bash
python -c "
from cassettify.ui.progress import ProgressApp
from cassettify.spotify import Track
t = Track(id='1', name='Test', artist='Artist', album='Album', album_art_url=None, spotify_url='')
app = ProgressApp([t], lambda t: True)
print('ProgressApp imported OK')
"
```

Expected: `ProgressApp imported OK`

- [ ] **Step 3: Commit**

```bash
git add cassettify/ui/progress.py
git commit -m "feat: download progress TUI"
```

---

## Task 10: App Orchestrator

**Files:**
- Create: `cassettify/ui/app.py`

- [ ] **Step 1: Implement `cassettify/ui/app.py`**

```python
from __future__ import annotations
import spotipy
from cassettify.config import Config
from cassettify.auth import get_client
from cassettify.spotify import get_playlists, get_tracks, Playlist
from cassettify import cache
from cassettify.downloader import download_track
from cassettify.ui.wizard import WizardApp
from cassettify.ui.picker import PickerApp
from cassettify.ui.progress import ProgressApp


def run_wizard() -> Config:
    """Run the first-run setup wizard. Saves and returns Config."""
    result = WizardApp().run()
    config = Config(
        client_id=result.client_id,
        client_secret=result.client_secret,
        output_dir=result.output_dir,
    )
    config.save()
    return config


def run_picker(sp: spotipy.Spotify) -> list[Playlist]:
    """Run the interactive playlist picker. Returns selected playlists."""
    playlists = get_playlists(sp)
    if not playlists:
        return []
    return PickerApp(playlists).run() or []


def run_downloads(
    sp: spotipy.Spotify, playlists: list[Playlist], output_dir: str
) -> None:
    """Collect tracks from playlists, skip cached, run the progress UI."""
    all_tracks = []
    for playlist in playlists:
        tracks = get_tracks(sp, playlist.id)
        new = [t for t in tracks if not cache.contains(t.id)]
        all_tracks.extend(new)

    if not all_tracks:
        print("Nothing new to download — all tracks already in cache.")
        return

    def download_and_cache(track):
        success = download_track(track, output_dir)
        if success:
            cache.add(track.id)
        return success

    ProgressApp(all_tracks, download_and_cache).run()
```

- [ ] **Step 2: Verify imports resolve**

```bash
python -c "from cassettify.ui.app import run_wizard, run_picker, run_downloads; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add cassettify/ui/app.py
git commit -m "feat: app orchestrator"
```

---

## Task 11: CLI Entry Point

**Files:**
- Create: `cassettify/cli.py`

- [ ] **Step 1: Implement `cassettify/cli.py`**

```python
from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer
from cassettify.config import Config
from cassettify.auth import get_client
from cassettify.spotify import get_playlists, find_playlist_by_name
from cassettify.ui.app import run_wizard, run_picker, run_downloads

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
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    if setup:
        run_wizard()
        return

    config = _ensure_config()
    output_dir = str(output) if output else config.output_dir
    sp = get_client(config)

    if all_playlists:
        playlists = get_playlists(sp)
    elif playlist:
        all_pls = get_playlists(sp)
        match = find_playlist_by_name(all_pls, playlist)
        if not match:
            typer.echo(f"Playlist '{playlist}' not found.", err=True)
            raise typer.Exit(code=1)
        playlists = [match]
    else:
        playlists = run_picker(sp)
        if not playlists:
            return

    run_downloads(sp, playlists, output_dir)
```

- [ ] **Step 2: Verify `--help` works**

```bash
cassettify --help
```

Expected output includes:
```
Usage: cassettify [OPTIONS] [PLAYLIST]
  Download your Spotify playlists for your iPod Classic.
Options:
  --all / --no-all   Download every playlist
  --output PATH      Output directory
  --setup            Re-run the first-time setup wizard
  --help             Show this message and exit.
```

- [ ] **Step 3: Run the full test suite**

```bash
pytest -v
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add cassettify/cli.py
git commit -m "feat: CLI entry point with typer"
```

---

## Task 12: Homebrew Formula

**Files:**
- Create: `Formula/cassettify.rb`

Note: The `sha256` and `url` fields below use placeholders — fill them in after the first PyPI release by running `sha256sum cassettify-0.1.0.tar.gz`.

- [ ] **Step 1: Create `Formula/cassettify.rb`**

```ruby
class Cassettify < Formula
  include Language::Python::Virtualenv

  desc "Download your Spotify playlists for your iPod Classic"
  homepage "https://github.com/bsolidgold/cassettify"
  url "https://files.pythonhosted.org/packages/source/c/cassettify/cassettify-0.1.0.tar.gz"
  sha256 "REPLACE_WITH_SHA256_AFTER_PYPI_RELEASE"
  license "MIT"

  depends_on "python@3.11"

  resource "spotipy" do
    url "https://files.pythonhosted.org/packages/source/s/spotipy/spotipy-2.23.0.tar.gz"
    sha256 "FILL_IN"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"cassettify", "--help"
  end
end
```

- [ ] **Step 2: Add README installation instructions**

Update `README.md`:

```markdown
# cassettify

Download your Spotify playlists for your iPod Classic.

## Install

```bash
# via pip
pip install cassettify

# via Homebrew
brew tap bsolidgold/cassettify
brew install cassettify
```

## Usage

```bash
cassettify                          # interactive playlist picker
cassettify "Dark Side of the Moon"  # download a specific playlist
cassettify --all                    # download everything
cassettify --output ~/Music/iPod    # set output directory
cassettify --setup                  # re-run setup wizard
```

Songs are saved as:  `<output>/<Artist>/<Album>/<track-number> - <title>.mp3`

## First run

Cassettify will walk you through connecting your Spotify account. You'll need
to create a free app at developer.spotify.com — the wizard explains exactly how.
```

- [ ] **Step 3: Commit**

```bash
git add Formula/cassettify.rb README.md
git commit -m "feat: homebrew formula and readme"
```

---

## Self-Review Notes

- All spec requirements covered: wizard, picker, progress TUI, `--all`, named playlist arg, `--output`, `--setup`, Artist/Album/Track folder structure, skip-if-cached, sequential downloads, failure logging.
- `Track`, `Playlist`, `WizardResult`, `Config` types are defined in Tasks 5, 7, and 2 respectively — all later tasks import them from those canonical locations.
- The Homebrew formula SHA256 is intentionally a placeholder — it cannot be filled in until after the first PyPI release.
- `download_track` uses `{artists}` (spotdl plural form) in the output template, which handles multi-artist tracks correctly.
