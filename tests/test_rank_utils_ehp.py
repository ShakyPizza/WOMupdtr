"""Tests for the EHP (skilling) rank ladder — Feature 2."""

import json

from python.utils import rank_utils


# ---------------------------------------------------------------------------
# Consolidated parser: EHP section
# ---------------------------------------------------------------------------

def test_get_rank_for_value_ehp_section(tmp_ranks_ini):
    assert rank_utils.get_rank_for_value(50, "Skilling Ranking") == "Wood"
    assert rank_utils.get_rank_for_value(150, "Skilling Ranking") == "Stone"
    assert rank_utils.get_rank_for_value(500, "Skilling Ranking") == "Steel"


def test_get_ehp_rank_wrapper(tmp_ranks_ini):
    assert rank_utils.get_ehp_rank(0) == "Wood"
    assert rank_utils.get_ehp_rank(100) == "Stone"


def test_get_rank_thresholds_unknown_section_returns_empty(tmp_ranks_ini):
    assert rank_utils.get_rank_thresholds("No Such Section") == []


def test_get_rank_for_value_boundary_semantics(tmp_ranks_ini):
    # lower bound inclusive, upper exclusive; the fixture's 0-99/100-199 ranges
    # leave a gap at exactly 99 which resolves to Unknown.
    assert rank_utils.get_rank_for_value(98, "Skilling Ranking") == "Wood"
    assert rank_utils.get_rank_for_value(100, "Skilling Ranking") == "Stone"
    assert rank_utils.get_rank_for_value(99, "Skilling Ranking") == "Unknown"


def test_next_rank_ehp(tmp_path, monkeypatch, tmp_ranks_ini):
    ranks_data = {"player": {"last_ehb": 10, "rank": "Bronze", "last_ehp": 150, "ehp_rank": "Stone"}}
    ranks_file = tmp_path / "player_ranks.json"
    ranks_file.write_text(json.dumps(ranks_data))
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    assert rank_utils.next_rank_ehp("player") == "Steel at 200 EHP"


def test_next_rank_ehp_max(tmp_path, monkeypatch, tmp_ranks_ini):
    ranks_data = {"player": {"last_ehb": 10, "rank": "Bronze", "last_ehp": 300, "ehp_rank": "Steel"}}
    ranks_file = tmp_path / "player_ranks.json"
    ranks_file.write_text(json.dumps(ranks_data))
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    assert rank_utils.next_rank_ehp("player") == "Max Rank Achieved 👑"


# ---------------------------------------------------------------------------
# save_ranks: EHP field preservation
# ---------------------------------------------------------------------------

def test_save_ranks_preserves_ehp_fields(tmp_path, monkeypatch):
    ranks_file = tmp_path / "player_ranks.json"
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))
    monkeypatch.setattr(rank_utils, "upsert_players", lambda players: None)

    data = {"player": {"last_ehb": 42, "rank": "Bronze", "last_ehp": 120, "ehp_rank": "Stone"}}
    rank_utils.save_ranks(data)

    assert json.loads(ranks_file.read_text()) == data


def test_save_ranks_omits_ehp_for_pre_ehp_rows(tmp_path, monkeypatch):
    """Rows without EHP keys round-trip byte-for-byte (backward compatible)."""
    ranks_file = tmp_path / "player_ranks.json"
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))
    monkeypatch.setattr(rank_utils, "upsert_players", lambda players: None)

    data = {"player": {"last_ehb": 42, "rank": "Bronze"}}
    rank_utils.save_ranks(data)

    assert json.loads(ranks_file.read_text()) == {"player": {"last_ehb": 42, "rank": "Bronze"}}


def test_save_ranks_syncs_on_ehp_change(tmp_path, monkeypatch):
    ranks_file = tmp_path / "player_ranks.json"
    ranks_file.write_text(json.dumps({"player": {"last_ehb": 42, "rank": "Bronze", "last_ehp": 100, "ehp_rank": "Stone"}}))
    monkeypatch.setattr(rank_utils, "RANKS_FILE", str(ranks_file))

    calls = []
    monkeypatch.setattr(rank_utils, "upsert_players", lambda players: calls.append(players))

    # EHB unchanged, EHP changed → must still sync
    rank_utils.save_ranks({"player": {"last_ehb": 42, "rank": "Bronze", "last_ehp": 130, "ehp_rank": "Stone"}})

    assert calls and "player" in calls[0]


# ---------------------------------------------------------------------------
# compute_member_update: independent EHB / EHP evaluation
# ---------------------------------------------------------------------------

def test_compute_member_update_ehb_increase():
    result = rank_utils.compute_member_update(
        {"last_ehb": 10, "rank": "Bronze"}, ehb=15, rank="Silver"
    )
    assert result["ehb_increase"] is True
    assert result["entry"]["last_ehb"] == 15
    assert result["entry"]["rank"] == "Silver"


def test_compute_member_update_stale_rank_correction():
    result = rank_utils.compute_member_update(
        {"last_ehb": 10, "rank": "Unknown"}, ehb=10, rank="Bronze"
    )
    assert result["ehb_increase"] is False
    assert result["entry"]["rank"] == "Bronze"


def test_compute_member_update_ehp_only_increase_not_swallowed():
    """Flat EHB but rising EHP must still register an EHP increase."""
    result = rank_utils.compute_member_update(
        {"last_ehb": 10, "rank": "Bronze", "last_ehp": 100, "ehp_rank": "Stone"},
        ehb=10,
        rank="Bronze",
        ehp=250,
        ehp_rank="Steel",
        track_ehp=True,
    )
    assert result["ehb_increase"] is False
    assert result["ehp_increase"] is True
    assert result["entry"]["last_ehp"] == 250
    assert result["entry"]["ehp_rank"] == "Steel"


def test_compute_member_update_ehp_untracked_leaves_ehp_alone():
    result = rank_utils.compute_member_update(
        {"last_ehb": 10, "rank": "Bronze", "last_ehp": 100, "ehp_rank": "Stone"},
        ehb=12,
        rank="Bronze",
        ehp=999,
        ehp_rank="Steel",
        track_ehp=False,
    )
    assert result["ehp_increase"] is False
    # untouched EHP fields preserved from last_data
    assert result["entry"]["last_ehp"] == 100
    assert result["entry"]["ehp_rank"] == "Stone"
