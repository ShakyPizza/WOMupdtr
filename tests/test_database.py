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


# ---------------------------------------------------------------------------
# Foundation F1 — column migration on an already-deployed table
# ---------------------------------------------------------------------------

def test_init_database_migrates_pre_existing_players_table(tmp_path):
    """A legacy players table (no EHP/status columns) gets columns added."""
    db_path = tmp_path / "database.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE players (
                username TEXT PRIMARY KEY,
                last_ehb REAL NOT NULL DEFAULT 0,
                rank TEXT NOT NULL DEFAULT 'Unknown',
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO players (username, last_ehb, rank, updated_at) VALUES ('alice', 5, 'Goblin', 'x')"
        )
        conn.commit()

    database.init_database(str(db_path))

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(players)")}
    for expected in {"last_ehp", "ehp_rank", "player_id", "wom_status", "last_changed_at"}:
        assert expected in columns


def test_init_database_is_idempotent(tmp_path):
    db_path = tmp_path / "database.db"
    database.init_database(str(db_path))
    # A second call must not raise (duplicate ALTER guarded by _ensure_columns).
    database.init_database(str(db_path))
    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(players)")}
    assert "last_ehp" in columns


def test_ehp_history_roundtrip(tmp_path):
    db_path = tmp_path / "database.db"
    database.log_ehp_history("alice", 120.0, timestamp="2025-01-01 12:00:00", db_path=str(db_path))
    database.log_ehp_history("alice", 130.0, timestamp="2025-02-01 12:00:00", db_path=str(db_path))

    history = database.read_player_ehp_history("alice", db_path=str(db_path))
    assert history == [
        {"timestamp": "2025-01-01 12:00:00", "ehp": 120.0},
        {"timestamp": "2025-02-01 12:00:00", "ehp": 130.0},
    ]


def test_upsert_players_persists_ehp_fields(tmp_path):
    db_path = tmp_path / "database.db"
    database.upsert_players(
        {"alice": {"last_ehb": 42.5, "rank": "Silver", "last_ehp": 300.0, "ehp_rank": "Adept"}},
        db_path=str(db_path),
    )
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT last_ehp, ehp_rank FROM players WHERE username = 'alice'"
        ).fetchone()
    assert row == (300.0, "Adept")
