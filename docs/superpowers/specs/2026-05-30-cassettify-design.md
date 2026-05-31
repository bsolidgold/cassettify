# Cassettify — Design Spec
*2026-05-30*

## Overview

Cassettify is a Python CLI tool that connects to your Spotify account, lets you browse and select playlists, and downloads the songs as tagged MP3s organized by `Artist/Album/Track` — ready to sync to an iPod Classic. It wraps `spotdl` for downloading and uses `textual` to render a rich, interactive terminal UI.

Distributed via PyPI (`pip install cassettify`) and Homebrew (`brew install cassettify`). Intended for personal use only.

---

## Architecture

A Python package with a single entry point (`cassettify`). Config and state live in `~/.cassettify/`. Three core runtime dependencies: `spotipy` (Spotify API), `spotdl` (download engine), `textual` + `rich` (TUI).

```
cassettify/
├── cassettify/
│   ├── cli.py          # entry point + typer commands
│   ├── auth.py         # Spotify OAuth, first-run wizard
│   ├── spotify.py      # playlist + track fetching via spotipy
│   ├── downloader.py   # spotdl subprocess wrapper
│   ├── config.py       # read/write ~/.cassettify/config.json
│   ├── cache.py        # downloaded-track registry (~/.cassettify/cache.json)
│   └── ui/
│       ├── app.py      # main Textual app
│       ├── wizard.py   # first-run setup screens
│       ├── picker.py   # playlist/track picker widget
│       └── progress.py # download progress display + album art
├── tests/
├── pyproject.toml
└── Formula/
    └── cassettify.rb   # Homebrew formula
```

---

## Dependencies

| Package | Role |
|---|---|
| `spotipy` | Spotify Web API — auth, playlists, track metadata |
| `spotdl` | Download engine — matches Spotify tracks to YouTube Music, downloads MP3, writes ID3 tags |
| `textual` | TUI framework — interactive widgets, layout, keyboard nav |
| `rich` | Text rendering, album art display in supported terminals (iTerm2) |
| `typer` | CLI argument parsing + help text |
| `requests` | Album art image fetching |

---

## CLI Interface

```bash
cassettify                          # launch full TUI
cassettify "Dark Side of the Moon"  # skip picker, download named playlist
cassettify --all                    # queue all playlists
cassettify --output ~/Music/iPod    # override default output directory
cassettify --setup                  # re-run first-run wizard
```

---

## Data Flow

### First run (no config)
1. Wizard launches in terminal
2. Step 1: Instructions to create a Spotify Developer app (client_id + client_secret)
3. Step 2: User pastes credentials → saved to `~/.cassettify/config.json`
4. Step 3: Browser opens for Spotify OAuth → token cached by spotipy
5. Step 4: "Where should songs be saved?" → default output path saved to config
6. Drops into main UI

### Normal run (config exists)
1. Spotify token refreshed silently if expired
2. Playlists fetched from Spotify API
3. Picker UI: browse, search, select one or many playlists
4. Track list fetched; each track checked against `~/.cassettify/cache.json`
5. Already-downloaded tracks skipped; new tracks queued
6. Download loop: one track at a time via spotdl subprocess
7. Progress UI updated live — album art, artist, album, track name, progress bar
8. On completion: track written to cache, filed as `<output>/<Artist>/<Album>/<track>.mp3`
9. End-of-session summary: downloaded, skipped, failed counts

---

## TUI Screens

### Wizard (first run)
Step-by-step guided setup. One question per screen. Styled prompts, inline validation, clear instructions for creating a Spotify app. Non-technical language throughout.

### Playlist Picker
Full-screen list of your Spotify playlists. Keyboard navigation, type-to-search, spacebar to select multiple, Enter to confirm. Shows playlist name, track count, and cover art thumbnail.

### Download Progress
```
┌─ cassettify ──────────────────────────────────────────┐
│  ▶ Downloading: Dark Side of the Moon                 │
│  ┌────────┐  Pink Floyd                               │
│  │  [art] │  The Dark Side of the Moon                │
│  │        │  ████████████░░░░░░░░  62%               │
│  └────────┘                                           │
│                                                       │
│  Queue (12 remaining)          ✓ Done (8)             │
│  • Money                       ✓ Speak to Me          │
│  • Any Colour You Like         ✓ Breathe              │
│  • Brain Damage                ✓ On the Run ...       │
└───────────────────────────────────────────────────────┘
```

Album art displays inline in iTerm2 and other terminals that support the Sixel or iTerm2 image protocol. Falls back to a text placeholder in unsupported terminals.

---

## Output Structure

```
<output_dir>/
└── Pink Floyd/
    └── The Dark Side of the Moon/
        ├── 01 - Speak to Me.mp3
        ├── 02 - Breathe.mp3
        └── ...
```

Track filenames use spotdl's default template: `{track-number} - {title}.{output-ext}`.

---

## State Files

| File | Purpose |
|---|---|
| `~/.cassettify/config.json` | Spotify credentials, default output path |
| `~/.cassettify/cache.json` | Set of downloaded track IDs (Spotify track IDs) |
| `~/.cassettify/failed.log` | Tracks that couldn't be matched or downloaded |
| `~/.cassettify/.spotify_cache` | spotipy OAuth token cache |

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Spotify token expired | Silent re-auth, continue |
| Track not found on YouTube Music | Log to `failed.log`, skip, continue |
| spotdl crashes on a track | Log to `failed.log`, skip, continue |
| No internet connection | Show clear error message, exit cleanly |
| Output directory doesn't exist | Create it automatically |
| Bad Spotify credentials on first run | Wizard catches it, prompt to re-enter |
| Duplicate track (appears in multiple playlists) | Cache hit — skip, no re-download |

No single track failure stops the queue. The download loop is resilient — finish what you can, log what you couldn't, report a summary at the end.

---

## Testing

| Layer | Approach |
|---|---|
| `config.py`, `cache.py` | Unit tests — pure logic, no I/O mocking needed |
| `spotify.py` | Mock tests — fake spotipy responses |
| `downloader.py` | Integration test with a known public playlist (optional, slow) |
| TUI | Manual — run it and verify visually |
| spotdl integration | Verified by running end-to-end |

---

## Distribution

### PyPI
- Package name: `cassettify`
- `pyproject.toml` with `[project.scripts]` entry point
- Published via `twine` / GitHub Actions on tag push

### Homebrew
- Formula at `Formula/cassettify.rb` in the repo
- Users tap via: `brew tap bretgold/cassettify && brew install cassettify`
- Formula installs the PyPI package via `pip` in a virtual env (standard pattern)
