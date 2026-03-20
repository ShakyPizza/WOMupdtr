"""Tests for python/web/services/csv_service.py."""

import csv
import pytest

from web.services import csv_service


# ---------------------------------------------------------------------------
# get_player_ehb_history
# ---------------------------------------------------------------------------

def test_get_player_ehb_history_returns_sorted_entries(monkeypatch, sample_csv_file):
    """History is returned sorted by timestamp ascending."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(sample_csv_file))

    history = csv_service.get_player_ehb_history("goblin_gaz")

    assert len(history) == 2
    assert history[0]["timestamp"] == "2025-01-01T10:00:00"
    assert history[1]["timestamp"] == "2025-02-01T10:00:00"
    assert history[0]["ehb"] == 3.0
    assert history[1]["ehb"] == 5.0


def test_get_player_ehb_history_case_insensitive(monkeypatch, sample_csv_file):
    """Username lookup is case-insensitive."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(sample_csv_file))

    history = csv_service.get_player_ehb_history("SILVER_SAM")

    assert len(history) == 2
    assert all(e["ehb"] for e in history)


def test_get_player_ehb_history_returns_empty_for_unknown_player(monkeypatch, sample_csv_file):
    """Unknown player returns an empty list."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(sample_csv_file))

    history = csv_service.get_player_ehb_history("no_such_player")

    assert history == []


def test_get_player_ehb_history_returns_empty_when_csv_missing(monkeypatch, tmp_path):
    """Missing CSV file returns an empty list without raising."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(tmp_path / "missing.csv"))

    history = csv_service.get_player_ehb_history("anyone")

    assert history == []


def test_get_player_ehb_history_skips_malformed_rows(monkeypatch, tmp_path):
    """Rows with non-numeric EHB or too few columns are skipped gracefully."""
    bad_csv = tmp_path / "bad.csv"
    with open(bad_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows([
            ["2025-01-01T10:00:00", "alpha", "not_a_number"],
            ["2025-01-02T10:00:00", "alpha"],                  # too short
            ["2025-01-03T10:00:00", "alpha", "50.0"],          # valid
        ])
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(bad_csv))

    history = csv_service.get_player_ehb_history("alpha")

    assert len(history) == 1
    assert history[0]["ehb"] == 50.0


# ---------------------------------------------------------------------------
# get_recent_changes
# ---------------------------------------------------------------------------

def test_get_recent_changes_returns_most_recent_first(monkeypatch, sample_csv_file):
    """Entries are sorted by timestamp descending."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(sample_csv_file))

    changes = csv_service.get_recent_changes()

    timestamps = [c["timestamp"] for c in changes]
    assert timestamps == sorted(timestamps, reverse=True)


def test_get_recent_changes_respects_limit(monkeypatch, sample_csv_file):
    """Only `limit` most recent entries are returned."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(sample_csv_file))

    changes = csv_service.get_recent_changes(limit=2)

    assert len(changes) == 2


def test_get_recent_changes_returns_all_when_fewer_than_limit(monkeypatch, sample_csv_file):
    """When total entries < limit, all entries are returned."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(sample_csv_file))

    changes = csv_service.get_recent_changes(limit=100)

    assert len(changes) == 5  # sample CSV has 5 rows


def test_get_recent_changes_includes_expected_keys(monkeypatch, sample_csv_file):
    """Each entry has timestamp, username, and ehb keys."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(sample_csv_file))

    changes = csv_service.get_recent_changes()

    for entry in changes:
        assert set(entry.keys()) >= {"timestamp", "username", "ehb"}


def test_get_recent_changes_returns_empty_when_csv_missing(monkeypatch, tmp_path):
    """Missing CSV returns empty list."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(tmp_path / "missing.csv"))

    changes = csv_service.get_recent_changes()

    assert changes == []


# ---------------------------------------------------------------------------
# get_all_ehb_entries
# ---------------------------------------------------------------------------

def test_get_all_ehb_entries_groups_by_player(monkeypatch, sample_csv_file):
    """Entries are grouped by username."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(sample_csv_file))

    grouped = csv_service.get_all_ehb_entries()

    assert set(grouped.keys()) == {"goblin_gaz", "silver_sam", "zenyte_zoe"}
    assert len(grouped["goblin_gaz"]) == 2
    assert len(grouped["silver_sam"]) == 2
    assert len(grouped["zenyte_zoe"]) == 1


def test_get_all_ehb_entries_sorted_within_group(monkeypatch, sample_csv_file):
    """Entries within each player group are sorted by timestamp ascending."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(sample_csv_file))

    grouped = csv_service.get_all_ehb_entries()

    for entries in grouped.values():
        timestamps = [e["timestamp"] for e in entries]
        assert timestamps == sorted(timestamps)


def test_get_all_ehb_entries_returns_empty_when_csv_missing(monkeypatch, tmp_path):
    """Missing CSV returns empty dict."""
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(tmp_path / "missing.csv"))

    grouped = csv_service.get_all_ehb_entries()

    assert grouped == {}


def test_get_all_ehb_entries_skips_malformed_rows(monkeypatch, tmp_path):
    """Malformed rows are skipped and valid rows are still returned."""
    bad_csv = tmp_path / "bad.csv"
    with open(bad_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows([
            ["2025-01-01T10:00:00", "beta", "bad"],
            ["2025-01-02T10:00:00", "beta", "75.0"],
        ])
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(bad_csv))

    grouped = csv_service.get_all_ehb_entries()

    assert "beta" in grouped
    assert len(grouped["beta"]) == 1
    assert grouped["beta"][0]["ehb"] == 75.0
