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
    with patch("cassettify.cache.CACHE_FILE", cache_file):
        assert cache.contains("track_123")
