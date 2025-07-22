import json
import os
import sys
import configparser
import pytest
import types

# Allow importing the 'python' package from the repository root

# Add repository root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Provide a minimal requests stub to satisfy imports when the real package is missing
requests_stub = types.SimpleNamespace(post=lambda *a, **k: None,
                                      get=lambda *a, **k: None,
                                      patch=lambda *a, **k: None)
sys.modules.setdefault('requests', requests_stub)

# Create a temporary config.ini so baserow_connect can import without errors
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
config_path = os.path.join(repo_root, "python", "config.ini")
with open(config_path, "w") as f:
    f.write("[baserow]\n")
    f.write("token = testtoken\n")

from python.utils import rank_utils


def test_load_ranks_converts_discord_names_to_list(tmp_path, monkeypatch):
    data = {
        "user1": {"last_ehb": 10, "rank": "Novice", "discord_name": "fan1"},
        "user2": {"last_ehb": 20, "rank": "Intermediate", "discord_name": ["fan2", "fan3"]},
        "user3": {"last_ehb": 30, "rank": "Advanced"}
    }
    ranks_file = tmp_path / "player_ranks.json"
    with open(ranks_file, "w") as f:
        json.dump(data, f)

    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    result = rank_utils.load_ranks()

    assert result["user1"]["discord_name"] == ["fan1"]
    assert result["user2"]["discord_name"] == ["fan2", "fan3"]
    assert result["user3"]["discord_name"] == []


def test_next_rank_returns_correct_next_rank(tmp_path, monkeypatch):
    ranks_data = {
        "player": {"last_ehb": 150, "rank": "Silver", "discord_name": []}
    }
    ranks_file = tmp_path / "player_ranks.json"
    with open(ranks_file, "w") as f:
        json.dump(ranks_data, f)
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    ranks_ini = tmp_path / "ranks.ini"
    with open(ranks_ini, "w") as f:
        f.write("[Group Ranking]\n")
        f.write("0-99 = Bronze\n")
        f.write("100-199 = Silver\n")
        f.write("200+ = Gold\n")

    original_read = configparser.ConfigParser.read

    def fake_read(self, filenames, encoding=None):
        return original_read(self, str(ranks_ini), encoding=encoding)

    monkeypatch.setattr(configparser.ConfigParser, "read", fake_read)

    result = rank_utils.next_rank("player")
    assert result == "Gold at 200 EHB"


def test_save_ranks_updates_baserow(tmp_path, monkeypatch):
    data = {"player": {"last_ehb": 42, "rank": "Bronze", "discord_name": []}}
    ranks_file = tmp_path / "player_ranks.json"
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    called = {}

    def fake_update(username, rank, ehb, discord_names):
        called["username"] = username
        called["rank"] = rank
        called["ehb"] = ehb
        called["discord"] = discord_names

    monkeypatch.setattr(rank_utils, "update_players_table", fake_update)

    rank_utils.save_ranks(data)

    assert called == {
        "username": "player",
        "rank": "Bronze",
        "ehb": 42,
        "discord": [],
    }
    with open(ranks_file) as f:
        assert json.load(f) == data
