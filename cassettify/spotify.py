from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import spotipy

LIKED_SONGS_ID = "__liked__"


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
    source_type: str = "playlist"  # "playlist" | "liked" | "album"


@dataclass
class Artist:
    id: str
    name: str
    cover_url: Optional[str]


def get_followed_artists(sp: spotipy.Spotify) -> list[Artist]:
    artists = []
    after = None
    while True:
        kwargs: dict = {"limit": 50}
        if after:
            kwargs["after"] = after
        results = sp.current_user_followed_artists(**kwargs)
        page = results["artists"]
        for a in page["items"]:
            cover = a["images"][0]["url"] if a["images"] else None
            artists.append(Artist(id=a["id"], name=a["name"], cover_url=cover))
        after = page.get("cursors", {}).get("after") if page.get("next") else None
        if not after:
            break
    return artists


def get_artist_albums(sp: spotipy.Spotify, artist_id: str) -> list[Playlist]:
    albums = []
    results = sp.artist_albums(artist_id, album_type="album,ep", limit=50)
    seen: set[str] = set()
    while results:
        for a in results["items"]:
            if a["id"] in seen:
                continue
            seen.add(a["id"])
            cover = a["images"][0]["url"] if a["images"] else None
            albums.append(Playlist(
                id=a["id"],
                name=a["name"],
                track_count=a["total_tracks"],
                cover_url=cover,
                source_type="album",
            ))
        results = sp.next(results) if results["next"] else None
    return albums


def get_all_sources(sp: spotipy.Spotify) -> list[Playlist]:
    """Liked songs + saved albums + user playlists as a flat list (used by --all)."""
    sources = []
    liked = sp.current_user_saved_tracks(limit=1)
    sources.append(Playlist(
        id=LIKED_SONGS_ID, name="♥  Liked Songs",
        track_count=liked["total"], cover_url=None, source_type="liked",
    ))
    results = sp.current_user_saved_albums(limit=50)
    while results:
        for item in results["items"]:
            a = item["album"]
            cover = a["images"][0]["url"] if a["images"] else None
            sources.append(Playlist(
                id=a["id"], name=a["name"],
                track_count=a["total_tracks"], cover_url=cover, source_type="album",
            ))
        results = sp.next(results) if results["next"] else None
    results = sp.current_user_playlists(limit=50)
    while results:
        for item in results["items"]:
            cover = item["images"][0]["url"] if item["images"] else None
            sources.append(Playlist(
                id=item["id"], name=item["name"],
                track_count=item["tracks"]["total"], cover_url=cover,
            ))
        results = sp.next(results) if results["next"] else None
    return sources


def get_tracks_for_source(sp: spotipy.Spotify, source: Playlist) -> list[Track]:
    if source.source_type == "liked":
        return _get_liked_tracks(sp)
    elif source.source_type == "album":
        return _get_album_tracks(sp, source.id)
    else:
        return get_tracks(sp, source.id)


def _get_liked_tracks(sp: spotipy.Spotify) -> list[Track]:
    tracks = []
    results = sp.current_user_saved_tracks(limit=50)
    while results:
        for item in results["items"]:
            t = item.get("track")
            if not t or not t.get("id"):
                continue
            spotify_url = t.get("external_urls", {}).get("spotify", "")
            if not spotify_url:
                continue
            art = t["album"]["images"][0]["url"] if t["album"]["images"] else None
            tracks.append(Track(
                id=t["id"], name=t["name"],
                artist=t["artists"][0]["name"] if t.get("artists") else "Unknown Artist",
                album=t["album"]["name"], album_art_url=art, spotify_url=spotify_url,
            ))
        results = sp.next(results) if results["next"] else None
    return tracks


def _get_album_tracks(sp: spotipy.Spotify, album_id: str) -> list[Track]:
    album = sp.album(album_id)
    album_name = album["name"]
    art = album["images"][0]["url"] if album["images"] else None
    tracks = []
    results = sp.album_tracks(album_id, limit=50)
    while results:
        for t in results["items"]:
            if not t or not t.get("id"):
                continue
            spotify_url = t.get("external_urls", {}).get("spotify", "")
            if not spotify_url:
                continue
            tracks.append(Track(
                id=t["id"], name=t["name"],
                artist=t["artists"][0]["name"] if t.get("artists") else "Unknown Artist",
                album=album_name, album_art_url=art, spotify_url=spotify_url,
            ))
        results = sp.next(results) if results["next"] else None
    return tracks


def get_playlists(sp: spotipy.Spotify) -> list[Playlist]:
    playlists = []
    results = sp.current_user_playlists(limit=50)
    while results:
        for item in results["items"]:
            cover = item["images"][0]["url"] if item["images"] else None
            playlists.append(Playlist(
                id=item["id"], name=item["name"],
                track_count=item["tracks"]["total"], cover_url=cover,
            ))
        results = sp.next(results) if results["next"] else None
    return playlists


def get_tracks(sp: spotipy.Spotify, playlist_id: str) -> list[Track]:
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    while results:
        for item in results["items"]:
            t = item.get("track")
            if not t or t.get("is_local") or not t.get("id"):
                continue
            spotify_url = t.get("external_urls", {}).get("spotify", "")
            if not spotify_url:
                continue
            art = t["album"]["images"][0]["url"] if t["album"]["images"] else None
            tracks.append(Track(
                id=t["id"], name=t["name"],
                artist=t["artists"][0]["name"] if t.get("artists") else "Unknown Artist",
                album=t["album"]["name"], album_art_url=art, spotify_url=spotify_url,
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
