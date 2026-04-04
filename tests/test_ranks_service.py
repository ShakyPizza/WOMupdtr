"""Tests for python/web/services/ranks_service.py."""

import configparser
import logging
import pytest

from web.services import ranks_service


# ---------------------------------------------------------------------------
# get_all_players_sorted
# ---------------------------------------------------------------------------

def test_get_all_players_sorted_returns_descending_ehb(monkeypatch, sample_players):
    """Players are returned sorted by EHB, highest first."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    result = ranks_service.get_all_players_sorted()

    assert [p["username"] for p in result] == ["zenyte_zoe", "silver_sam", "goblin_gaz"]
    assert result[0]["ehb"] == 1600.0
    assert result[-1]["ehb"] == 5.0


def test_get_all_players_sorted_returns_empty_list_when_no_players(monkeypatch):
    """Empty ranks dict produces an empty list."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: {})

    result = ranks_service.get_all_players_sorted()

    assert result == []


def test_get_all_players_sorted_includes_expected_keys(monkeypatch, sample_players):
    """Each player dict contains username, ehb, rank, and discord_name."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    result = ranks_service.get_all_players_sorted()

    for player in result:
        assert set(player.keys()) >= {"username", "ehb", "rank", "discord_name"}


def test_get_all_players_sorted_defaults_missing_fields(monkeypatch):
    """Players with missing fields get default values."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: {
        "blank": {}
    })

    result = ranks_service.get_all_players_sorted()

    assert result[0]["ehb"] == 0
    assert result[0]["rank"] == "Unknown"
    assert result[0]["discord_name"] == []


def test_get_rank_snapshot_reports_load_errors(monkeypatch, caplog):
    """Snapshot exposes a user-facing error when rank loading fails."""
    def explode():
        raise RuntimeError("bad ranks")

    monkeypatch.setattr(ranks_service, "load_ranks", explode)

    with caplog.at_level(logging.ERROR):
        snapshot = ranks_service.get_rank_snapshot()

    assert snapshot.players == []
    assert snapshot.rank_distribution == {}
    assert snapshot.error is not None
    assert "could not be loaded" in snapshot.error.lower()
    assert "Failed to load player ranks" in caplog.text


# ---------------------------------------------------------------------------
# get_player_detail
# ---------------------------------------------------------------------------

def test_get_player_detail_returns_correct_data(monkeypatch, sample_players):
    """Known player is returned with all expected fields."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)
    monkeypatch.setattr(ranks_service, "next_rank", lambda username: "Opal at 10 EHB")

    result = ranks_service.get_player_detail("goblin_gaz")

    assert result is not None
    assert result["username"] == "goblin_gaz"
    assert result["ehb"] == 5.0
    assert result["rank"] == "Goblin"
    assert result["next_rank"] == "Opal at 10 EHB"


def test_get_player_detail_case_insensitive(monkeypatch, sample_players):
    """Lookup is case-insensitive."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)
    monkeypatch.setattr(ranks_service, "next_rank", lambda username: "Max Rank Achieved 👑")

    result = ranks_service.get_player_detail("ZENYTE_ZOE")

    assert result is not None
    assert result["username"] == "zenyte_zoe"


def test_get_player_detail_returns_none_for_unknown(monkeypatch, sample_players):
    """Unknown player returns None."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    result = ranks_service.get_player_detail("nobody")

    assert result is None


# ---------------------------------------------------------------------------
# get_rank_distribution
# ---------------------------------------------------------------------------

def test_get_rank_distribution_counts_per_rank(monkeypatch, sample_players):
    """Distribution dict maps rank name to player count."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    dist = ranks_service.get_rank_distribution()

    assert dist == {"Goblin": 1, "Silver": 1, "Zenyte": 1}


def test_get_rank_distribution_aggregates_multiple_players_in_same_rank(monkeypatch):
    """Multiple players at the same rank are counted correctly."""
    data = {
        "a": {"rank": "Bronze"},
        "b": {"rank": "Bronze"},
        "c": {"rank": "Silver"},
    }
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: data)

    dist = ranks_service.get_rank_distribution()

    assert dist["Bronze"] == 2
    assert dist["Silver"] == 1


def test_get_rank_distribution_empty(monkeypatch):
    """Empty player dict returns empty distribution."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: {})

    dist = ranks_service.get_rank_distribution()

    assert dist == {}


# ---------------------------------------------------------------------------
# search_players
# ---------------------------------------------------------------------------

def test_search_players_substring_match(monkeypatch, sample_players):
    """Substring query returns only matching players."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    result = ranks_service.search_players("silver")

    assert len(result) == 1
    assert result[0]["username"] == "silver_sam"


def test_search_players_case_insensitive(monkeypatch, sample_players):
    """Query is matched case-insensitively."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    result = ranks_service.search_players("GOBLIN")

    assert len(result) == 1
    assert result[0]["username"] == "goblin_gaz"


def test_search_players_empty_query_returns_all(monkeypatch, sample_players):
    """Empty query returns all players sorted by EHB."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    result = ranks_service.search_players("")

    assert len(result) == 3


def test_search_players_no_match_returns_empty(monkeypatch, sample_players):
    """Query with no matches returns empty list."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    result = ranks_service.search_players("xxxxxx")

    assert result == []


def test_search_players_partial_prefix(monkeypatch, sample_players):
    """Partial prefix matches correctly."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    result = ranks_service.search_players("zen")

    assert len(result) == 1
    assert result[0]["username"] == "zenyte_zoe"


def test_search_players_supports_name_sort(monkeypatch, sample_players):
    """Name sort returns alphabetical usernames."""
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    result = ranks_service.search_players("", sort="name")

    assert [player["username"] for player in result] == ["goblin_gaz", "silver_sam", "zenyte_zoe"]


# ---------------------------------------------------------------------------
# get_rank_thresholds
# ---------------------------------------------------------------------------

def test_get_rank_thresholds_parses_ranges(monkeypatch, ranks_ini_file):
    """Bounded ranges are parsed into lower/upper/name dicts."""
    original_read = configparser.ConfigParser.read

    def fake_read(self, filenames, encoding=None):
        return original_read(self, str(ranks_ini_file), encoding=encoding)

    monkeypatch.setattr(configparser.ConfigParser, "read", fake_read)

    thresholds = ranks_service.get_rank_thresholds()

    goblin = next(t for t in thresholds if t["name"] == "Goblin")
    assert goblin["lower"] == 0
    assert goblin["upper"] == 10


def test_get_rank_thresholds_parses_open_ended(monkeypatch, ranks_ini_file):
    """Open-ended ranges (e.g. 1500+) have upper=None."""
    original_read = configparser.ConfigParser.read

    def fake_read(self, filenames, encoding=None):
        return original_read(self, str(ranks_ini_file), encoding=encoding)

    monkeypatch.setattr(configparser.ConfigParser, "read", fake_read)

    thresholds = ranks_service.get_rank_thresholds()

    zenyte = next(t for t in thresholds if t["name"] == "Zenyte")
    assert zenyte["lower"] == 1500
    assert zenyte["upper"] is None


def test_get_rank_thresholds_sorted_by_lower_bound(monkeypatch, ranks_ini_file):
    """Thresholds are returned in ascending order of lower bound."""
    original_read = configparser.ConfigParser.read

    def fake_read(self, filenames, encoding=None):
        return original_read(self, str(ranks_ini_file), encoding=encoding)

    monkeypatch.setattr(configparser.ConfigParser, "read", fake_read)

    thresholds = ranks_service.get_rank_thresholds()
    lower_bounds = [t["lower"] for t in thresholds]

    assert lower_bounds == sorted(lower_bounds)
