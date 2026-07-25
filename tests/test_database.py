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
    assert {
        "players",
        "ehb_history",
        "wom_players",
        "player_aliases",
        "achievements",
    }.issubset(tables)


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
    for expected in {
        "last_ehp",
        "ehp_rank",
        "total_xp",
        "player_id",
        "wom_status",
        "last_changed_at",
    }:
        assert expected in columns
    with sqlite3.connect(db_path) as conn:
        total_xp = conn.execute(
            "SELECT total_xp FROM players WHERE username = 'alice'"
        ).fetchone()[0]
    assert total_xp is None


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


def test_upsert_players_persists_total_xp_without_erasing_it_when_omitted(tmp_path):
    db_path = tmp_path / "database.db"
    database.upsert_players(
        {"alice": {"last_ehb": 42.5, "rank": "Silver", "total_xp": 123456789}},
        db_path=str(db_path),
    )
    database.upsert_players(
        {"alice": {"last_ehb": 43.0, "rank": "Silver"}},
        db_path=str(db_path),
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT last_ehb, total_xp FROM players WHERE username = 'alice'"
        ).fetchone()
    assert row == (43.0, 123456789)


def test_upsert_achievement_events_normalizes_identity_and_alias(tmp_path):
    db_path = tmp_path / "database.db"
    row = {
        "player_id": 42,
        "source_group_id": 7,
        "current_username": "hero player",
        "display_name": "Hero Player",
        "account_type": "ironman",
        "build": "main",
        "status": "active",
        "overall_xp": 123_456_789,
        "metric": "Wintertodt",
        "measure": "Kills",
        "threshold": 500,
        "name": "500 Wintertodt kills",
        "achieved_at": "2025-01-02T03:04:05+00:00",
        "accuracy_ms": 1200,
        "legacy": False,
    }

    assert database.upsert_achievement_events([row], db_path=str(db_path)) == 1

    with sqlite3.connect(db_path) as conn:
        player = conn.execute(
            "SELECT player_id, display_name, account_type, overall_xp FROM wom_players"
        ).fetchone()
        alias = conn.execute(
            "SELECT player_id, normalized_name, display_name FROM player_aliases"
        ).fetchone()
        achievement = conn.execute(
            """
            SELECT player_id, source_group_id, metric, measure, threshold,
                   name, accuracy_ms, legacy
            FROM achievements
            """
        ).fetchone()

    assert player == (42, "Hero Player", "ironman", 123_456_789)
    assert alias == (42, "hero player", "Hero Player")
    assert achievement == (
        42,
        7,
        "wintertodt",
        "kills",
        500,
        "500 Wintertodt kills",
        1200,
        0,
    )


def test_upsert_achievement_events_deduplicates_and_updates_mutable_fields(tmp_path):
    db_path = tmp_path / "database.db"
    base = {
        "player_id": 42,
        "source_group_id": 7,
        "display_name": "Old Name",
        "metric": "agility",
        "measure": "experience",
        "threshold": 50_000_000,
        "name": "50m Agility",
        "achieved_at": "2025-01-01T00:00:00+00:00",
        "accuracy_ms": 5000,
        "legacy": False,
    }
    assert database.upsert_achievement_events([base], db_path=str(db_path)) == 1

    updated = {
        **base,
        "display_name": "New Name",
        "achieved_at": "2025-01-01T01:00:00+00:00",
        "accuracy_ms": 1000,
        "legacy": True,
    }
    assert database.upsert_achievement_events([updated], db_path=str(db_path)) == 0
    missing_optional_fields = {
        **updated,
        "achieved_at": None,
        "accuracy_ms": None,
        "legacy": None,
    }
    assert (
        database.upsert_achievement_events(
            [missing_optional_fields],
            db_path=str(db_path),
        )
        == 0
    )

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM achievements").fetchone()[0]
        achievement = conn.execute(
            "SELECT achieved_at, accuracy_ms, legacy FROM achievements"
        ).fetchone()
        aliases = {
            row[0] for row in conn.execute("SELECT normalized_name FROM player_aliases")
        }

    assert count == 1
    assert achievement == ("2025-01-01T01:00:00+00:00", 1000, 1)
    assert aliases == {"old name", "new name"}


def test_achievement_dedup_key_includes_threshold(tmp_path):
    db_path = tmp_path / "database.db"
    base = {
        "player_id": 42,
        "source_group_id": 7,
        "metric": "zulrah",
        "measure": "kills",
        "name": "Zulrah milestone",
    }
    inserted = database.upsert_achievement_events(
        [
            {**base, "threshold": 100},
            {**base, "threshold": 500},
        ],
        db_path=str(db_path),
    )
    assert inserted == 2
