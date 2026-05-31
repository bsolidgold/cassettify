# 🎵 cassettify

Download your Spotify library to tagged MP3s — organized, art-embedded, and ready to play anywhere.

Cassettify connects to your Spotify account and gives you an interactive terminal UI to browse your **playlists, liked songs, saved albums, and followed artists**, pick exactly what you want, and download it via YouTube Music (using [spotdl](https://github.com/spotDL/spotify-downloader)). Downloads run in the background with an animated cassette-tape progress screen while you keep browsing.

Songs land as:

```
<output>/<Artist>/<Album>/<track-number> - <title>.mp3
```

with full ID3 tags and embedded album art.

---

## Install

The recommended way is with [pipx](https://pipx.pypa.io), which installs Cassettify in its own isolated environment and puts a global `cassettify` command on your PATH:

```bash
pipx install cassettify
```

Don't have pipx?

```bash
brew install pipx                     # macOS
# or:  python3 -m pip install --user pipx && python3 -m pipx ensurepath
```

Or just use plain pip (into the current environment):

```bash
pip install cassettify
```

---

## Quick start

```bash
cassettify
```

On first launch, a setup wizard connects your Spotify account (see **First run** below), then drops you into the library browser.

---

## Command-line options

```bash
cassettify                           # interactive library browser
cassettify "Dark Side of the Moon"   # download a specific playlist by name, skip the browser
cassettify --all                     # queue every playlist
cassettify --output ~/Music/Downloads     # use this output folder for this run only
cassettify --set-output ~/Music/Downloads # permanently change the output folder (offers to move your library)
cassettify --setup                   # re-run the setup wizard (re-auth, change folder, move library)
cassettify --cookies auto            # grab YouTube cookies from your browser (see Rate limits)
cassettify --cookies chrome          # ...or from a specific browser
```

| Option | Description |
|---|---|
| `[playlist]` | Name of a playlist to download directly, skipping the browser |
| `--all`, `-a` | Queue every one of your playlists |
| `--output`, `-o PATH` | Override the output directory for this run |
| `--set-output PATH` | Change the saved output directory, with an option to move your existing library |
| `--setup` | Re-run the setup wizard |
| `--cookies [browser]` | Extract YouTube cookies from a browser (`auto` to auto-detect) and exit |

---

## Browsing & selecting music

Launching `cassettify` with no arguments opens the library browser. The top level has four categories:

- **♥ Liked Songs** — your saved tracks
- **◈ Playlists** — your Spotify playlists
- **▣ Saved Albums** — albums you've saved
- **♪ Followed Artists** — artists you follow → their albums

Drill into any playlist, album, or artist to pick **individual songs**, or select a whole source at once. Your selections are preserved as you navigate in and out — pick a few songs from one playlist, back out, grab an album, and they all stay selected.

### Keyboard controls

**In a list (categories / playlists / albums / artists):**

| Key | Action |
|---|---|
| `↑` / `↓` | Move the cursor |
| `Enter` | Drill in (browse the tracks / albums inside) |
| `Space` | Select the entire source (all its tracks) |
| `/` | Search the list (`Esc` closes search) |
| `D` | Start/open downloads for everything you've selected |
| `Esc` | Go back a level (quits from the top level) |

**When picking individual tracks:**

| Key | Action |
|---|---|
| `Space` | Toggle the highlighted track |
| `A` | Select all |
| `N` | Select none |
| `D` | Download everything selected |
| `Esc` | Save your picks and go back |

---

## Downloading in the background

Press **`D`** anytime to start downloading what you've selected. The cassette screen shows the current track, an animated spinning reel, a live status (searching → downloading → tagging) with an elapsed timer, the remaining queue, and what's finished.

Downloads keep running in the background:

- **`Esc`** on the cassette screen returns you to the library — **downloads keep going.** A status line at the top shows progress while you browse.
- **`D`** again reopens the cassette and **adds any newly-selected songs** to the running queue.
- Songs already downloaded (or queued, or selected from two places) are **never downloaded twice**.
- **`Q`** quits.

Tracks already on disk are skipped on future runs, so re-running is always safe.

---

## First run

The setup wizard walks you through connecting a free Spotify app:

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and log in
2. Click **Create app**
3. Set the **Redirect URI** to exactly:
   ```
   https://127.0.0.1:8888/callback
   ```
4. Copy your **Client ID** and **Client Secret** and paste them into the wizard
5. Choose where to save your music

When you authorize, your browser opens to Spotify and a local HTTPS server catches the response automatically (you'll see a one-time self-signed-certificate warning — click **Advanced → Proceed**). No copy-pasting URLs.

Credentials are saved to `~/.cassettify/config.json` with owner-only permissions. You won't need to set up again.

---

## Changing where music is saved

Two ways:

```bash
cassettify --set-output ~/Music/Downloads
```

This updates the saved default and, if your old folder has music, asks whether to move it. Or re-run `cassettify --setup` — the folder step pre-fills your current location and offers a **"Move my existing tracks"** checkbox.

Moving preserves the `Artist/Album/Track` structure and never overwrites — anything already present at the destination is left untouched.

---

## Rate limits & cookies

YouTube may rate-limit you after downloading a lot of tracks quickly ("you might be blocked…"). The fix is to download using your logged-in browser session:

```bash
cassettify --cookies auto      # auto-detect your browser
cassettify --cookies chrome    # or name it: chrome / safari / firefox / edge / brave / ...
```

Cassettify also tries this automatically on first run. Cookies are read straight from your browser (no manual export) and saved to `~/.cassettify/cookies.txt`, which every download then uses.

- **Chrome on macOS** prompts for Keychain access the first time — click *Always Allow*.
- **Safari** needs your terminal to have Full Disk Access (System Settings → Privacy & Security).

If a block is already in effect, adding cookies (or simply waiting ~30–60 min) clears it.

---

## Files & state

| Path | What it holds |
|---|---|
| `~/.cassettify/config.json` | Spotify credentials + saved output folder (owner-only) |
| `~/.cassettify/cache.json` | IDs of already-downloaded tracks (so they're skipped) |
| `~/.cassettify/cookies.txt` | YouTube cookies used for downloads |
| `~/.cassettify/failed.log` | Tracks that couldn't be matched or downloaded |
| `~/.cassettify/.spotify_cache` | Cached Spotify OAuth token |

---

## Requirements

- Python 3.11+
- A free [Spotify Developer](https://developer.spotify.com) app (Client ID + Secret)
- Internet connection

---

## Notes

Audio is sourced from YouTube Music via spotdl. Cassettify is intended for **personal archival use only** — please respect the terms of service of the platforms involved.

---

## License

MIT
