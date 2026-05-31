# cassettify

Download your Spotify playlists to MP3 — organized and tagged, ready for your iPod Classic.

Connects to your Spotify account, shows your playlists in an interactive terminal UI, and downloads everything via YouTube Music using [spotdl](https://github.com/spotDL/spotify-downloader). Songs land in `Artist/Album/Track.mp3` format with full ID3 tags.

---

## Install

```bash
pip install cassettify
```

Or via Homebrew:

```bash
brew tap bsolidgold/cassettify
brew install cassettify
```

---

## Usage

```bash
cassettify                           # browse and pick playlists interactively
cassettify "Dark Side of the Moon"   # download a specific playlist by name
cassettify --all                     # download every playlist
cassettify --output ~/Music/iPod     # override the output directory
cassettify --setup                   # re-run the first-time setup wizard
```

Songs are saved as:

```
<output>/<Artist>/<Album>/<track-number> - <title>.mp3
```

Already-downloaded tracks are skipped on subsequent runs, so re-running is safe.

---

## First run

The first time you run `cassettify`, a setup wizard walks you through connecting your Spotify account:

1. Create a free app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Set the Redirect URI to `http://localhost:8888/callback`
3. Paste your Client ID and Client Secret into the wizard
4. Pick a folder for your music

Your credentials are saved to `~/.cassettify/config.json` (owner-readable only). You won't need to set up again.

---

## Requirements

- Python 3.11+
- A free [Spotify Developer](https://developer.spotify.com) app (Client ID + Secret)
- Internet connection

---

## Notes

Downloads are sourced from YouTube Music via spotdl. This tool is intended for personal archival use only. Please respect the terms of service of the platforms involved.

Failed downloads are logged to `~/.cassettify/failed.log` so you can review anything that didn't match.

---

## License

MIT
