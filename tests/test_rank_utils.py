import json
import os
import sys
import configparser
import pytest

# Allow importing the 'python' package from the repository root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
