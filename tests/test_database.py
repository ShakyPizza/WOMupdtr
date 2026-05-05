"""Tests for python/utils/database.py."""

import sqlite3

from python.utils import database


def test_init_database_creates_expected_tables(tmp_path):
    db_path = tmp_path / "database.db"

    resolved = database.init_database(str(db_path))

    assert resolved == str(db_path)
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert {"players", "ehb_history"}.issubset(tables)


def test_upsert_players_writes_snapshot_rows(tmp_path):
    db_path = tmp_path / "database.db"

    database.upsert_players(
        {"alice": {"last_ehb": 42.5, "rank": "Silver"}},
        db_path=str(db_path),
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT username, last_ehb, rank FROM players WHERE username = ?",
            ("alice",),
        ).fetchone()
    assert row == ("alice", 42.5, "Silver")


def test_log_ehb_history_inserts_row(tmp_path):
    db_path = tmp_path / "database.db"

    database.log_ehb_history("alice", 99.0, timestamp="2025-01-01 12:00:00", db_path=str(db_path))

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT timestamp, username, ehb FROM ehb_history WHERE username = ?",
            ("alice",),
        ).fetchone()
    assert row == ("2025-01-01 12:00:00", "alice", 99.0)


def test_import_csv_history_skips_duplicates(tmp_path, monkeypatch):
    db_path = tmp_path / "database.db"
    csv_path = tmp_path / "ehb_log.csv"
    csv_path.write_text(
        "2025-01-01 10:00:00,alice,10.0\n"
        "2025-01-01 10:00:00,alice,10.0\n"
        "2025-01-02 10:00:00,bob,20.0\n"
    )
    monkeypatch.setenv("EHB_LOG_PATH", str(csv_path))

    imported = database.import_csv_history(db_path=str(db_path))

    assert imported == 2
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM ehb_history").fetchone()[0]
    assert count == 2
