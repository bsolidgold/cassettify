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
