"""SQLite persistence helpers for WOMupdtr."""

from __future__ import annotations

import csv
import os
import sqlite3
from contextlib import closing
from datetime import datetime

DEFAULT_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database.db")


def resolve_db_path() -> str:
    """Return the configured SQLite database path."""
    return os.environ.get("WOM_DATABASE_PATH", DEFAULT_DB_FILE)


def connect_db(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with row access enabled."""
    conn = sqlite3.connect(db_path or resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_history_csv_path(file_name: str) -> str:
    """Resolve the EHB CSV path without importing log_csv and creating a cycle."""
    env_path = os.environ.get("EHB_LOG_PATH")
    if env_path:
        return env_path
    if os.path.isabs(file_name):
        return file_name
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_dir, file_name)


def init_database(db_path: str | None = None) -> str:
    """Create the SQLite database and required tables if they do not exist."""
    resolved_path = db_path or resolve_db_path()
    os.makedirs(os.path.dirname(resolved_path), exist_ok=True)

    with closing(connect_db(resolved_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                username TEXT PRIMARY KEY,
                last_ehb REAL NOT NULL DEFAULT 0,
                rank TEXT NOT NULL DEFAULT 'Unknown',
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ehb_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                username TEXT NOT NULL,
                ehb REAL NOT NULL,
                UNIQUE(timestamp, username, ehb)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ehb_history_username_ts ON ehb_history (username, timestamp)"
        )
        conn.commit()

    return resolved_path


def upsert_players(players: dict[str, dict], db_path: str | None = None) -> None:
    """Persist the latest player snapshot to SQLite."""
    if not players:
        return

    resolved_path = init_database(db_path)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with closing(connect_db(resolved_path)) as conn:
        conn.executemany(
            """
            INSERT INTO players (username, last_ehb, rank, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                last_ehb = excluded.last_ehb,
                rank = excluded.rank,
                updated_at = excluded.updated_at
            """,
            [
                (
                    username,
                    float(data.get("last_ehb", 0)),
                    str(data.get("rank", "Unknown")),
                    timestamp,
                )
                for username, data in players.items()
            ],
        )
        conn.commit()


def log_ehb_history(username: str, ehb: float, timestamp: str | None = None, db_path: str | None = None) -> None:
    """Insert one EHB history row into SQLite."""
    resolved_path = init_database(db_path)
    recorded_at = timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with closing(connect_db(resolved_path)) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO ehb_history (timestamp, username, ehb)
            VALUES (?, ?, ?)
            """,
            (recorded_at, username, float(ehb)),
        )
        conn.commit()


def import_csv_history(db_path: str | None = None, file_name: str = "ehb_log.csv") -> int:
    """Import existing CSV history into SQLite, skipping duplicates."""
    resolved_path = init_database(db_path)
    resolved_csv = _resolve_history_csv_path(file_name)
    if not os.path.exists(resolved_csv):
        return 0

    imported = 0
    with open(resolved_csv, mode="r", newline="", encoding="utf-8") as file_obj:
        rows = list(csv.reader(file_obj))

    with closing(connect_db(resolved_path)) as conn:
        for row in rows:
            if len(row) < 3:
                continue
            timestamp = row[0].strip()
            username = row[1].strip()
            try:
                ehb = float(row[2].strip())
            except ValueError:
                continue
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO ehb_history (timestamp, username, ehb)
                VALUES (?, ?, ?)
                """,
                (timestamp, username, ehb),
            )
            imported += cursor.rowcount
        conn.commit()
    return imported


def count_players(db_path: str | None = None) -> int:
    """Return the number of player snapshot rows in SQLite."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM players").fetchone()
    return int(row["count"]) if row else 0
