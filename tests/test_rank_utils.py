import json
import os
import sys
import configparser
import pytest

# Allow importing the 'python' package from the repository root

# Add repository root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from python.utils import rank_utils


@pytest.fixture(autouse=True)
def reset_bootstrapped_flag():
    """Reset global CSV-bootstrap flag before and after every test."""
    rank_utils._BOOTSTRAPPED_FROM_CSV = False
    yield
    rank_utils._BOOTSTRAPPED_FROM_CSV = False


@pytest.fixture
def tmp_ranks_ini(tmp_path, monkeypatch):
    """Write a minimal ranks.ini to tmp_path and redirect configparser.read to it."""
    ranks_ini = tmp_path / "ranks.ini"
    with open(ranks_ini, "w") as f:
        f.write("[Group Ranking]\n")
        f.write("0-99 = Bronze\n")
        f.write("100-199 = Silver\n")
        f.write("200+ = Gold\n")
        f.write("\n")
        f.write("[Skilling Ranking]\n")
        f.write("0-99 = Wood\n")
        f.write("100-199 = Stone\n")
        f.write("200+ = Steel\n")

    original_read = configparser.ConfigParser.read

    def fake_read(self, filenames, encoding=None):
        return original_read(self, str(ranks_ini), encoding=encoding)

    monkeypatch.setattr(configparser.ConfigParser, "read", fake_read)
    return ranks_ini


def test_load_ranks_preserves_json_payload(tmp_path, monkeypatch):
    data = {
        "user1": {"last_ehb": 10, "rank": "Novice"},
        "user2": {"last_ehb": 20, "rank": "Intermediate"},
        "user3": {"last_ehb": 30, "rank": "Advanced"}
    }
    ranks_file = tmp_path / "player_ranks.json"
    with open(ranks_file, "w") as f:
        json.dump(data, f)

    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    result = rank_utils.load_ranks()

    assert result == data


def test_load_ranks_restores_ehp_baseline_from_sqlite_after_restart(tmp_path, monkeypatch):
    """A missing container-local JSON file must not reset persisted EHP state."""
    ranks_file = tmp_path / "missing-player-ranks.json"
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))
    rank_utils.upsert_players(
        {
            "alice": {
                "last_ehb": 42.5,
                "rank": "Silver",
                "last_ehp": 300.0,
                "ehp_rank": "Adept",
                "total_xp": 123456789,
            }
        }
    )

    ranks = rank_utils.load_ranks()
    update = rank_utils.compute_member_update(
        ranks["alice"],
        ehb=42.5,
        rank="Silver",
        ehp=300.0,
        ehp_rank="Adept",
        track_ehp=True,
        total_xp=123456789,
    )

    assert update["ehp_increase"] is False
    assert update["ehp_old_rank"] == "Adept"
    assert not ranks_file.exists()


def test_load_ranks_migrates_legacy_json_when_database_is_empty(tmp_path, monkeypatch):
    legacy = {
        "alice": {
            "last_ehb": 42.5,
            "rank": "Silver",
            "last_ehp": 300.0,
            "ehp_rank": "Adept",
        }
    }
    ranks_file = tmp_path / "player_ranks.json"
    ranks_file.write_text(json.dumps(legacy))
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    assert rank_utils.load_ranks() == legacy

    ranks_file.unlink()
    assert rank_utils.load_ranks() == legacy


def test_status_only_database_rows_do_not_block_legacy_migration(tmp_path, monkeypatch):
    from python.utils.database import upsert_player_status

    upsert_player_status([{"username": "status-only", "wom_status": "active"}])
    legacy = {"alice": {"last_ehb": 42.5, "rank": "Silver"}}
    ranks_file = tmp_path / "player_ranks.json"
    ranks_file.write_text(json.dumps(legacy))
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    assert rank_utils.load_ranks() == legacy


def test_save_ranks_does_not_recreate_legacy_json(tmp_path, monkeypatch):
    ranks_file = tmp_path / "player_ranks.json"
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    data = {"alice": {"last_ehb": 42.5, "rank": "Silver"}}
    rank_utils.save_ranks(data)

    assert rank_utils.load_ranks()["alice"]["last_ehb"] == 42.5
    assert not ranks_file.exists()


def test_save_ranks_propagates_sqlite_failures(monkeypatch):
    def fail_write(_players):
        raise OSError("database is read-only")

    monkeypatch.setattr(rank_utils, "upsert_players", fail_write)

    with pytest.raises(OSError, match="database is read-only"):
        rank_utils.save_ranks({"alice": {"last_ehb": 42.5, "rank": "Silver"}})


def test_next_rank_returns_correct_next_rank(tmp_path, monkeypatch):
    ranks_data = {
        "player": {"last_ehb": 150, "rank": "Silver"}
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


def test_save_ranks_updates_sqlite_snapshot(tmp_path, monkeypatch):
    """save_ranks sends the sanitized snapshot to SQLite without rewriting JSON."""
    initial = {"player": {"last_ehb": 10, "rank": "Bronze"}}
    ranks_file = tmp_path / "player_ranks.json"
    with open(ranks_file, "w") as f:
        json.dump(initial, f)

    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    updated = {"player": {"last_ehb": 42, "rank": "Bronze"}}

    called = {}

    def fake_update(players):
        ((username, pdata),) = players.items()
        called["username"] = username
        called["rank"] = pdata["rank"]
        called["ehb"] = pdata["last_ehb"]

    monkeypatch.setattr(rank_utils, "upsert_players", fake_update)

    rank_utils.save_ranks(updated)

    assert called == {
        "username": "player",
        "rank": "Bronze",
        "ehb": 42,
    }
    with open(ranks_file) as f:
        assert json.load(f) == initial


def test_save_ranks_persists_complete_snapshot_when_ehb_unchanged(tmp_path, monkeypatch):
    """SQLite receives the complete snapshot so it remains authoritative."""

    data = {"player": {"last_ehb": 42, "rank": "Bronze"}}
    ranks_file = tmp_path / "player_ranks.json"
    with open(ranks_file, "w") as f:
        json.dump(data, f)

    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    calls = []

    def fake_update(players):
        calls.append(players)

    monkeypatch.setattr(rank_utils, "upsert_players", fake_update)

    rank_utils.save_ranks(data)

    assert calls == [data]


def test_save_ranks_persists_and_upserts_total_xp_change(tmp_path, monkeypatch):
    ranks_file = tmp_path / "player_ranks.json"
    ranks_file.write_text(
        json.dumps({"player": {"last_ehb": 42, "rank": "Bronze"}})
    )
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    calls = []
    monkeypatch.setattr(rank_utils, "upsert_players", lambda players: calls.append(players))

    updated = {
        "player": {
            "last_ehb": 42,
            "rank": "Bronze",
            "total_xp": 123456789,
        }
    }
    rank_utils.save_ranks(updated)

    assert calls == [updated]
    assert json.loads(ranks_file.read_text()) == {
        "player": {"last_ehb": 42, "rank": "Bronze"}
    }


def test_load_ranks_returns_empty_on_corrupt_json(tmp_path, monkeypatch):
    ranks_file = tmp_path / "player_ranks.json"
    with open(ranks_file, "w") as f:
        f.write("{bad json")

    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))
    monkeypatch.setattr("python.utils.rank_utils.load_latest_ehb_from_csv", lambda: {})

    result = rank_utils.load_ranks()

    assert result == {}


def test_next_rank_returns_unknown_for_missing_user(tmp_path, monkeypatch):
    ranks_file = tmp_path / "player_ranks.json"
    with open(ranks_file, "w") as f:
        json.dump({}, f)

    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    result = rank_utils.next_rank("missing_player")

    assert result == "Unknown"


def test_next_rank_returns_max_rank_when_at_top(tmp_path, monkeypatch):
    ranks_data = {
        "player": {"last_ehb": 150, "rank": "Gold"}
    }
    ranks_file = tmp_path / "player_ranks.json"
    with open(ranks_file, "w") as f:
        json.dump(ranks_data, f)
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    ranks_ini = tmp_path / "ranks.ini"
    with open(ranks_ini, "w") as f:
        f.write("[Group Ranking]\n")
        f.write("0-99 = Bronze\n")
        f.write("100+ = Gold\n")

    original_read = configparser.ConfigParser.read

    def fake_read(self, filenames, encoding=None):
        return original_read(self, str(ranks_ini), encoding=encoding)

    monkeypatch.setattr(configparser.ConfigParser, "read", fake_read)

    result = rank_utils.next_rank("player")

    assert result == "Max Rank Achieved 👑"


def test_save_ranks_persists_all_players_in_one_batch(tmp_path, monkeypatch):
    old_data = {
        "alpha": {"last_ehb": 10, "rank": "Bronze"},
        "beta": {"last_ehb": 20, "rank": "Silver"},
    }
    ranks_file = tmp_path / "player_ranks.json"
    with open(ranks_file, "w") as f:
        json.dump(old_data, f)

    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    new_data = {
        "alpha": {"last_ehb": 10, "rank": "Bronze"},
        "beta": {"last_ehb": 25, "rank": "Silver"},
    }

    calls = []

    def fake_update(players):
        calls.extend((username, pdata["rank"], pdata["last_ehb"]) for username, pdata in players.items())

    monkeypatch.setattr(rank_utils, "upsert_players", fake_update)

    rank_utils.save_ranks(new_data)

    assert calls == [
        ("alpha", "Bronze", 10),
        ("beta", "Silver", 25),
    ]


# --- _get_rank_for_ehb ---

def test_get_rank_for_ehb_mid_range(tmp_ranks_ini):
    assert rank_utils._get_rank_for_ehb(150) == "Silver"


def test_get_rank_for_ehb_exactly_at_lower_boundary(tmp_ranks_ini):
    # 100 is the lower bound of Silver (100-199), should return Silver not Bronze
    assert rank_utils._get_rank_for_ehb(100) == "Silver"


def test_get_rank_for_ehb_open_ended_range(tmp_ranks_ini):
    assert rank_utils._get_rank_for_ehb(500) == "Gold"


def test_get_rank_for_ehb_below_all_thresholds(tmp_ranks_ini):
    # EHB of 0 is within 0-99, should return Bronze
    assert rank_utils._get_rank_for_ehb(0) == "Bronze"


def test_get_rank_for_ehb_returns_unknown_when_no_match(tmp_path, monkeypatch):
    # ranks.ini only covers 100+, so EHB of 50 matches nothing
    ranks_ini = tmp_path / "ranks.ini"
    with open(ranks_ini, "w") as f:
        f.write("[Group Ranking]\n")
        f.write("100+ = Gold\n")

    original_read = configparser.ConfigParser.read

    def fake_read(self, filenames, encoding=None):
        return original_read(self, str(ranks_ini), encoding=encoding)

    monkeypatch.setattr(configparser.ConfigParser, "read", fake_read)

    assert rank_utils._get_rank_for_ehb(50) == "Unknown"


# --- save_ranks with corrupt existing file ---

def test_save_ranks_treats_all_as_new_when_existing_file_corrupt(tmp_path, monkeypatch):
    """When the on-disk JSON is corrupt at save time, old_data is empty so every player triggers a sync."""
    ranks_file = tmp_path / "player_ranks.json"
    with open(ranks_file, "w") as f:
        f.write("{bad json")

    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    new_data = {"player": {"last_ehb": 42, "rank": "Silver"}}

    calls = []

    def fake_update(players):
        calls.extend((username, pdata["rank"], pdata["last_ehb"]) for username, pdata in players.items())

    monkeypatch.setattr(rank_utils, "upsert_players", fake_update)

    rank_utils.save_ranks(new_data)

    assert calls == [("player", "Silver", 42)]
