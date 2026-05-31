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

Songs are saved as: `<output>/<Artist>/<Album>/<track-number> - <title>.mp3`

## First run

Cassettify will walk you through connecting your Spotify account. You'll need
to create a free app at developer.spotify.com — the wizard explains exactly how.

## Notes

Downloads via YouTube Music. Intended for personal archival use only.
