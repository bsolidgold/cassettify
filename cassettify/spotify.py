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
