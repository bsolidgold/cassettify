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
