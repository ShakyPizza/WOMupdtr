"""Additional tests for python/utils/rank_utils.py filling coverage gaps."""

import json
import os
import sys
import configparser
import pytest

# Allow importing the 'python' package from the repository root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from python.utils import rank_utils


@pytest.fixture(autouse=True)
def reset_bootstrapped_flag():
    """Reset the global CSV-bootstrap flag before and after every test."""
    rank_utils._BOOTSTRAPPED_FROM_CSV = False
    yield
    rank_utils._BOOTSTRAPPED_FROM_CSV = False


@pytest.fixture
def tmp_ranks_ini(tmp_path, monkeypatch):
    """Write a minimal ranks.ini and redirect all ConfigParser.read calls to it."""
    ranks_ini = tmp_path / "ranks.ini"
    ranks_ini.write_text(
        "[Group Ranking]\n"
        "0-99 = Bronze\n"
        "100-199 = Silver\n"
        "200+ = Gold\n"
    )
    original_read = configparser.ConfigParser.read

    def fake_read(self, filenames, encoding=None):
        return original_read(self, str(ranks_ini), encoding=encoding)

    monkeypatch.setattr(configparser.ConfigParser, "read", fake_read)
    return ranks_ini


# ---------------------------------------------------------------------------
# save_ranks — first run (no existing JSON)
# ---------------------------------------------------------------------------

def test_save_ranks_creates_file_on_first_run(tmp_path, monkeypatch):
    """save_ranks writes a new file when player_ranks.json does not yet exist."""
    json_path = tmp_path / "player_ranks.json"
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(json_path))

    calls = []
    monkeypatch.setattr(rank_utils, "upsert_players", lambda players: calls.append(players))

    data = {"alice": {"last_ehb": 50.0, "rank": "Bronze"}}
    rank_utils.save_ranks(data)

    assert json_path.exists()
    saved = json.loads(json_path.read_text())
    assert saved["alice"]["last_ehb"] == 50.0


def test_save_ranks_syncs_to_sqlite_on_first_run(tmp_path, monkeypatch):
    """When JSON file is absent all players are treated as new and synced."""
    json_path = tmp_path / "player_ranks.json"
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(json_path))

    calls = []
    monkeypatch.setattr(rank_utils, "upsert_players", lambda players: calls.append(players))

    data = {"alice": {"last_ehb": 50.0, "rank": "Bronze"}}
    rank_utils.save_ranks(data)

    # alice's old_ehb is None (no file existed), current is 50 → sync triggered
    assert len(calls) == 1
    assert list(calls[0].keys()) == ["alice"]


# ---------------------------------------------------------------------------
# next_rank — boundary cases
# ---------------------------------------------------------------------------

def test_next_rank_at_exact_lower_boundary(tmp_path, monkeypatch, tmp_ranks_ini):
    """Player with EHB exactly at the threshold of a rank returns the correct next rank."""
    json_path = tmp_path / "player_ranks.json"
    # EHB = 100 puts the player exactly at the Silver threshold (100-199)
    data = {"boundary_bob": {"last_ehb": 100.0, "rank": "Silver"}}
    json_path.write_text(json.dumps(data))
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(json_path))

    result = rank_utils.next_rank("boundary_bob")

    assert result == "Gold at 200 EHB"


def test_next_rank_for_unknown_user_returns_unknown(tmp_path, monkeypatch, tmp_ranks_ini):
    """next_rank returns 'Unknown' for a player not in the ranks data."""
    json_path = tmp_path / "player_ranks.json"
    json_path.write_text(json.dumps({}))
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(json_path))

    result = rank_utils.next_rank("ghost")

    assert result == "Unknown"


# ---------------------------------------------------------------------------
# _bootstrap_ranks_from_csv
# ---------------------------------------------------------------------------

def test_bootstrap_ranks_from_csv_sets_flag(tmp_path, monkeypatch, tmp_ranks_ini):
    """After bootstrapping from CSV the global flag is set to True."""
    csv_data = {"zara": 250.0}
    monkeypatch.setattr(rank_utils, "load_latest_ehb_from_csv", lambda: csv_data)

    rank_utils._bootstrap_ranks_from_csv()

    assert rank_utils._BOOTSTRAPPED_FROM_CSV is True


def test_bootstrap_ranks_from_csv_builds_correct_entries(tmp_path, monkeypatch, tmp_ranks_ini):
    """Bootstrap builds rank entries for each player in the CSV."""
    csv_data = {"zara": 150.0}
    monkeypatch.setattr(rank_utils, "load_latest_ehb_from_csv", lambda: csv_data)

    result = rank_utils._bootstrap_ranks_from_csv()

    assert "zara" in result
    assert result["zara"]["last_ehb"] == 150.0
    assert result["zara"]["rank"] == "Silver"


def test_bootstrap_ranks_from_csv_returns_empty_when_no_csv(monkeypatch):
    """When CSV is empty/missing bootstrap returns an empty dict."""
    monkeypatch.setattr(rank_utils, "load_latest_ehb_from_csv", lambda: {})

    result = rank_utils._bootstrap_ranks_from_csv()

    assert result == {}
    assert rank_utils._BOOTSTRAPPED_FROM_CSV is False


def test_save_ranks_syncs_after_bootstrap_when_data_changes(tmp_path, monkeypatch):
    """save_ranks still syncs SQLite after bootstrap when new data is written."""
    json_path = tmp_path / "player_ranks.json"
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(json_path))

    calls = []
    monkeypatch.setattr(rank_utils, "upsert_players", lambda players: calls.append(players))

    rank_utils._BOOTSTRAPPED_FROM_CSV = True
    data = {"alice": {"last_ehb": 50.0, "rank": "Bronze"}}
    rank_utils.save_ranks(data)

    assert len(calls) == 1
    assert list(calls[0].keys()) == ["alice"]


# ---------------------------------------------------------------------------
# load_ranks — edge cases
# ---------------------------------------------------------------------------

def test_load_ranks_empty_file_falls_back_to_bootstrap(tmp_path, monkeypatch):
    """load_ranks handles a zero-byte JSON file gracefully without raising."""
    json_path = tmp_path / "player_ranks.json"
    json_path.write_text("")
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(json_path))
    monkeypatch.setattr(rank_utils, "load_latest_ehb_from_csv", lambda: {})

    result = rank_utils.load_ranks()

    assert result == {}


def test_load_ranks_preserves_unrecognized_fields(tmp_path, monkeypatch):
    """load_ranks returns stored JSON without schema mutation."""
    json_path = tmp_path / "player_ranks.json"
    data = {"dan": {"last_ehb": 10.0, "rank": "Bronze", "note": "legacy"}}
    json_path.write_text(json.dumps(data))
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(json_path))

    result = rank_utils.load_ranks()

    assert result == data


def test_load_ranks_missing_optional_fields_is_accepted(tmp_path, monkeypatch):
    """load_ranks accepts entries with only the core rank fields."""
    json_path = tmp_path / "player_ranks.json"
    data = {"eve": {"last_ehb": 20.0, "rank": "Bronze"}}
    json_path.write_text(json.dumps(data))
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(json_path))

    result = rank_utils.load_ranks()

    assert result == data
