"""SQLite persistence helpers for WOMupdtr."""

from __future__ import annotations

import csv
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

DEFAULT_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database.db")

# SQLite cannot bind table/column names as parameters, so identifiers used in
# DDL are interpolated directly. Restrict them to a safe character set so the
# f-strings below can never carry injected SQL, even if a caller is changed.
_SQL_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _assert_identifier(value: str) -> str:
    """Return ``value`` if it is a safe SQL identifier, else raise ``ValueError``."""
    if not _SQL_IDENTIFIER.match(value):
        raise ValueError(f"Unsafe SQL identifier: {value!r}")
    return value


def resolve_db_path() -> str:
    """Return the configured SQLite database path."""
    return os.environ.get("WOM_DATABASE_PATH", DEFAULT_DB_FILE)


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    """Idempotently add missing columns to an existing table.

    ``CREATE TABLE IF NOT EXISTS`` is a no-op on an already-deployed database, so
    it never adds new columns. This helper inspects the live schema and issues
    ``ALTER TABLE ... ADD COLUMN`` only for columns that are not present yet.
    """
    _assert_identifier(table)
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query,python.lang.security.audit.formatted-sql-query.formatted-sql-query -- identifier validated above; PRAGMA cannot use bound parameters
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, ddl in columns.items():
        if name not in existing:
            _assert_identifier(name)
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query,python.lang.security.audit.formatted-sql-query.formatted-sql-query -- table/column validated; ALTER TABLE cannot use bound parameters
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


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

        # EHP, total XP, and inactivity/status tracking add columns to the
        # existing ``players`` table. On a fresh database the CREATE above does
        # not include them, and on a deployed database the CREATE is a no-op, so
        # the migration helper is the single source of truth for these columns.
        _ensure_columns(
            conn,
            "players",
            {
                # Feature 2 — skilling (EHP) rank ladder
                "last_ehp": "REAL NOT NULL DEFAULT 0",
                "ehp_rank": "TEXT NOT NULL DEFAULT 'Unknown'",
                "total_xp": "INTEGER",
                "snapshot_initialized": "INTEGER NOT NULL DEFAULT 0",
                # Feature 3 — inactivity / status detection
                "player_id": "INTEGER",
                "wom_status": "TEXT",
                "last_changed_at": "TEXT",
                "wom_updated_at": "TEXT",
                "last_progressed_at": "TEXT",
                "status_captured_at": "TEXT",
            },
        )
        # Existing databases predate the explicit snapshot marker. Infer it
        # from non-default rank data without marking status-only player rows.
        conn.execute(
            """
            UPDATE players
            SET snapshot_initialized = 1
            WHERE snapshot_initialized = 0
              AND (
                  last_ehb != 0 OR rank != 'Unknown'
                  OR last_ehp != 0 OR ehp_rank != 'Unknown'
                  OR total_xp IS NOT NULL
              )
            """
        )

        # Feature 2 — EHP history (mirror of ehb_history)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ehp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                username TEXT NOT NULL,
                ehp REAL NOT NULL,
                UNIQUE(timestamp, username, ehp)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ehp_history_username_ts ON ehp_history (username, timestamp)"
        )

        # Feature 1 — per-boss leaderboards / kill history
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS boss_kills_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                boss TEXT NOT NULL,
                username TEXT NOT NULL,
                kills INTEGER NOT NULL,
                rank INTEGER,
                UNIQUE(timestamp, boss, username)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_boss_kills_boss_ts ON boss_kills_history (boss, timestamp)"
        )

        # Feature 4 — persisted gains snapshots
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gains_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_time TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                username TEXT NOT NULL,
                metric TEXT NOT NULL,
                gained REAL NOT NULL,
                UNIQUE(snapshot_time, username, metric)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gains_metric_ts ON gains_history (metric, snapshot_time)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gains_user_metric_ts ON gains_history (username, metric, snapshot_time)"
        )

        # Phase 1 achievement retention uses WOM's stable numeric player ID.
        # The existing username-keyed ``players`` table remains the rank
        # projection for backward compatibility.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wom_players (
                player_id INTEGER PRIMARY KEY,
                current_username TEXT,
                display_name TEXT,
                account_type TEXT,
                build TEXT,
                status TEXT,
                overall_xp INTEGER,
                ehp REAL,
                ehb REAL,
                ttm REAL,
                tt200m REAL,
                registered_at TEXT,
                wom_updated_at TEXT,
                last_changed_at TEXT,
                last_imported_at TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_aliases (
                player_id INTEGER NOT NULL,
                normalized_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                PRIMARY KEY (player_id, normalized_name)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_player_aliases_name ON player_aliases (normalized_name)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                source_group_id INTEGER NOT NULL,
                metric TEXT NOT NULL,
                measure TEXT NOT NULL,
                threshold INTEGER NOT NULL,
                name TEXT NOT NULL,
                achieved_at TEXT,
                accuracy_ms INTEGER,
                legacy INTEGER NOT NULL DEFAULT 0,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                UNIQUE(player_id, metric, measure, threshold)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_achievements_player_ts ON achievements (player_id, achieved_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_achievements_metric_ts ON achievements (metric, measure, achieved_at)"
        )

        # Central audit log for every outbound Wise Old Man API call (see
        # utils.api_usage). Added after the 2026-07 IP-block incident so
        # request volume is visible in real time instead of only after a ban.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_call_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                method TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                status_code INTEGER,
                duration_ms INTEGER,
                outcome TEXT NOT NULL,
                user_agent TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_call_log_ts ON api_call_log (timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_call_log_endpoint_ts ON api_call_log (endpoint, timestamp)"
        )
        # ``user_agent`` was added after the table's initial rollout; back-fill
        # it on any database created before that so INSERTs don't fail on a
        # missing column.
        _ensure_columns(conn, "api_call_log", {"user_agent": "TEXT"})

        conn.commit()

    return resolved_path


def upsert_players(players: dict[str, dict], db_path: str | None = None) -> None:
    """Persist the latest player rank snapshot (EHB + EHP + total XP) to SQLite."""
    if not players:
        return

    resolved_path = init_database(db_path)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with closing(connect_db(resolved_path)) as conn:
        conn.executemany(
            """
            INSERT INTO players (
                username, last_ehb, rank, last_ehp, ehp_rank, total_xp,
                snapshot_initialized, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(username) DO UPDATE SET
                last_ehb = excluded.last_ehb,
                rank = excluded.rank,
                last_ehp = excluded.last_ehp,
                ehp_rank = excluded.ehp_rank,
                total_xp = COALESCE(excluded.total_xp, players.total_xp),
                snapshot_initialized = 1,
                updated_at = excluded.updated_at
            """,
            [
                (
                    username,
                    float(data.get("last_ehb", 0)),
                    str(data.get("rank", "Unknown")),
                    float(data.get("last_ehp", 0)),
                    str(data.get("ehp_rank", "Unknown")),
                    int(data["total_xp"]) if data.get("total_xp") is not None else None,
                    timestamp,
                )
                for username, data in players.items()
            ],
        )
        conn.commit()


def read_player_snapshots(db_path: str | None = None) -> dict[str, dict]:
    """Return the latest persisted EHB, EHP, and total-XP state by username."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        rows = conn.execute(
            """
            SELECT username, last_ehb, rank, last_ehp, ehp_rank, total_xp
            FROM players
            WHERE snapshot_initialized = 1
            """
        ).fetchall()

    snapshots = {}
    for row in rows:
        snapshot = {
            "last_ehb": row["last_ehb"],
            "rank": row["rank"],
        }
        if row["last_ehp"] != 0 or row["ehp_rank"] != "Unknown":
            snapshot["last_ehp"] = row["last_ehp"]
            snapshot["ehp_rank"] = row["ehp_rank"]
        if row["total_xp"] is not None:
            snapshot["total_xp"] = row["total_xp"]
        snapshots[row["username"]] = snapshot
    return snapshots


def upsert_player_status(rows: list[dict], db_path: str | None = None) -> None:
    """Persist per-player WOM status/activity metadata (Feature 3).

    Touches only the status/activity columns so it can be called independently of
    :func:`upsert_players` without clobbering the rank snapshot.
    """
    if not rows:
        return

    resolved_path = init_database(db_path)
    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with closing(connect_db(resolved_path)) as conn:
        conn.executemany(
            """
            INSERT INTO players (
                username, player_id, wom_status, last_changed_at,
                wom_updated_at, last_progressed_at, status_captured_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                player_id = excluded.player_id,
                wom_status = excluded.wom_status,
                last_changed_at = excluded.last_changed_at,
                wom_updated_at = excluded.wom_updated_at,
                last_progressed_at = excluded.last_progressed_at,
                status_captured_at = excluded.status_captured_at
            """,
            [
                (
                    str(row.get("username")),
                    row.get("player_id"),
                    row.get("wom_status"),
                    row.get("last_changed_at"),
                    row.get("wom_updated_at"),
                    row.get("last_progressed_at"),
                    captured_at,
                    captured_at,
                )
                for row in rows
                if row.get("username")
            ],
        )
        conn.commit()


def read_player_status_rows(db_path: str | None = None) -> list[dict]:
    """Return persisted per-player status/activity rows (Feature 3).

    Threshold classification (inactivity, fallback chain, timezone handling) is
    performed by :mod:`utils.inactivity`; this reader only surfaces the raw rows.
    """
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        rows = conn.execute(
            """
            SELECT username, last_ehb, rank, player_id, wom_status,
                   last_changed_at, wom_updated_at, last_progressed_at, status_captured_at
            FROM players
            """
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_achievement_events(rows: list[dict], db_path: str | None = None) -> int:
    """Persist normalized WOM players, aliases, and achievement events.

    Achievement identity intentionally excludes display text and timestamps:
    WOM can recalculate ``achieved_at``/``accuracy_ms`` without creating a new
    milestone. The stable key is player + metric + measure + threshold.
    Returns the number of newly inserted achievement rows.
    """
    if not rows:
        return 0

    resolved_path = init_database(db_path)
    observed_at = datetime.now(timezone.utc).isoformat()
    inserted = 0

    with closing(connect_db(resolved_path)) as conn:
        for row in rows:
            try:
                player_id = int(row["player_id"])
                source_group_id = int(row["source_group_id"])
                metric = str(row["metric"]).strip().lower()
                measure = str(row["measure"]).strip().lower()
                threshold = int(row["threshold"])
            except (KeyError, TypeError, ValueError):
                continue
            if not metric or not measure:
                continue

            current_username = row.get("current_username")
            display_name = row.get("display_name") or current_username
            legacy_value = row.get("legacy")
            legacy_for_update = (
                None if legacy_value is None else (1 if legacy_value else 0)
            )
            conn.execute(
                """
                INSERT INTO wom_players (
                    player_id, current_username, display_name, account_type,
                    build, status, overall_xp, ehp, ehb, ttm, tt200m,
                    registered_at, wom_updated_at, last_changed_at,
                    last_imported_at, first_seen_at, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    current_username = COALESCE(excluded.current_username, wom_players.current_username),
                    display_name = COALESCE(excluded.display_name, wom_players.display_name),
                    account_type = COALESCE(excluded.account_type, wom_players.account_type),
                    build = COALESCE(excluded.build, wom_players.build),
                    status = COALESCE(excluded.status, wom_players.status),
                    overall_xp = COALESCE(excluded.overall_xp, wom_players.overall_xp),
                    ehp = COALESCE(excluded.ehp, wom_players.ehp),
                    ehb = COALESCE(excluded.ehb, wom_players.ehb),
                    ttm = COALESCE(excluded.ttm, wom_players.ttm),
                    tt200m = COALESCE(excluded.tt200m, wom_players.tt200m),
                    registered_at = COALESCE(excluded.registered_at, wom_players.registered_at),
                    wom_updated_at = COALESCE(excluded.wom_updated_at, wom_players.wom_updated_at),
                    last_changed_at = COALESCE(excluded.last_changed_at, wom_players.last_changed_at),
                    last_imported_at = COALESCE(excluded.last_imported_at, wom_players.last_imported_at),
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    player_id,
                    current_username,
                    display_name,
                    row.get("account_type"),
                    row.get("build"),
                    row.get("status"),
                    row.get("overall_xp"),
                    row.get("ehp"),
                    row.get("ehb"),
                    row.get("ttm"),
                    row.get("tt200m"),
                    row.get("registered_at"),
                    row.get("wom_updated_at"),
                    row.get("last_changed_at"),
                    row.get("last_imported_at"),
                    observed_at,
                    observed_at,
                ),
            )

            if display_name:
                normalized_name = str(display_name).strip().casefold()
                if normalized_name:
                    conn.execute(
                        """
                        INSERT INTO player_aliases (
                            player_id, normalized_name, display_name,
                            first_seen_at, last_seen_at
                        )
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(player_id, normalized_name) DO UPDATE SET
                            display_name = excluded.display_name,
                            last_seen_at = excluded.last_seen_at
                        """,
                        (
                            player_id,
                            normalized_name,
                            str(display_name).strip(),
                            observed_at,
                            observed_at,
                        ),
                    )

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO achievements (
                    player_id, source_group_id, metric, measure, threshold,
                    name, achieved_at, accuracy_ms, legacy,
                    first_seen_at, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    player_id,
                    source_group_id,
                    metric,
                    measure,
                    threshold,
                    str(row.get("name") or f"{threshold} {metric} {measure}"),
                    row.get("achieved_at"),
                    row.get("accuracy_ms"),
                    legacy_for_update or 0,
                    observed_at,
                    observed_at,
                ),
            )
            inserted += cursor.rowcount
            if cursor.rowcount == 0:
                conn.execute(
                    """
                    UPDATE achievements
                    SET source_group_id = ?,
                        name = ?,
                        achieved_at = COALESCE(?, achieved_at),
                        accuracy_ms = COALESCE(?, accuracy_ms),
                        legacy = COALESCE(?, legacy),
                        last_seen_at = ?
                    WHERE player_id = ? AND metric = ? AND measure = ? AND threshold = ?
                    """,
                    (
                        source_group_id,
                        str(row.get("name") or f"{threshold} {metric} {measure}"),
                        row.get("achieved_at"),
                        row.get("accuracy_ms"),
                        legacy_for_update,
                        observed_at,
                        player_id,
                        metric,
                        measure,
                        threshold,
                    ),
                )

        conn.commit()
    return inserted


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


def log_ehp_history(username: str, ehp: float, timestamp: str | None = None, db_path: str | None = None) -> None:
    """Insert one EHP history row into SQLite (Feature 2)."""
    resolved_path = init_database(db_path)
    recorded_at = timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with closing(connect_db(resolved_path)) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO ehp_history (timestamp, username, ehp)
            VALUES (?, ?, ?)
            """,
            (recorded_at, username, float(ehp)),
        )
        conn.commit()


def read_player_ehp_history(username: str, db_path: str | None = None) -> list[dict]:
    """Return ``[{timestamp, ehp}]`` for a player, ordered by time (Feature 2)."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        rows = conn.execute(
            """
            SELECT timestamp, ehp FROM ehp_history
            WHERE username = ? COLLATE NOCASE
            ORDER BY timestamp
            """,
            (username,),
        ).fetchall()
    return [{"timestamp": row["timestamp"], "ehp": row["ehp"]} for row in rows]


# ---------------------------------------------------------------------------
# Feature 1 — per-boss leaderboards / kill history
# ---------------------------------------------------------------------------


def log_boss_kills(boss: str, rows: list[dict], timestamp: str | None = None, db_path: str | None = None) -> None:
    """Persist a boss-kill leaderboard snapshot.

    ``rows`` is a list of ``{username, kills, rank}`` dicts. The ``UNIQUE`` index
    on ``(timestamp, boss, username)`` makes repeated writes of the same snapshot
    idempotent.
    """
    if not rows:
        return

    resolved_path = init_database(db_path)
    recorded_at = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with closing(connect_db(resolved_path)) as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO boss_kills_history (timestamp, boss, username, kills, rank)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    recorded_at,
                    boss,
                    str(row.get("username")),
                    int(row.get("kills", 0)),
                    row.get("rank"),
                )
                for row in rows
                if row.get("username")
            ],
        )
        conn.commit()


def get_boss_leaderboard(boss: str, db_path: str | None = None) -> list[dict]:
    """Return the latest stored leaderboard for ``boss`` (kills descending)."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        latest = conn.execute(
            "SELECT MAX(timestamp) AS ts FROM boss_kills_history WHERE boss = ?",
            (boss,),
        ).fetchone()
        if not latest or latest["ts"] is None:
            return []
        rows = conn.execute(
            """
            SELECT username, kills, rank, timestamp
            FROM boss_kills_history
            WHERE boss = ? AND timestamp = ?
            ORDER BY kills DESC, username
            """,
            (boss, latest["ts"]),
        ).fetchall()
    return [dict(row) for row in rows]


def get_boss_history(boss: str, username: str, db_path: str | None = None) -> list[dict]:
    """Return ``[{timestamp, kills}]`` history for one player at one boss."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        rows = conn.execute(
            """
            SELECT timestamp, kills FROM boss_kills_history
            WHERE boss = ? AND username = ? COLLATE NOCASE
            ORDER BY timestamp
            """,
            (boss, username),
        ).fetchall()
    return [{"timestamp": row["timestamp"], "kills": row["kills"]} for row in rows]


def list_tracked_bosses(db_path: str | None = None) -> list[str]:
    """Return the distinct bosses that have stored kill snapshots."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        rows = conn.execute(
            "SELECT DISTINCT boss FROM boss_kills_history ORDER BY boss"
        ).fetchall()
    return [row["boss"] for row in rows]


# ---------------------------------------------------------------------------
# Feature 4 — persisted gains snapshots
# ---------------------------------------------------------------------------


def log_gains_snapshot(rows: list[dict], db_path: str | None = None) -> int:
    """Persist gains-snapshot rows.

    ``rows`` is a list of ``{snapshot_time, period_start, period_end, username,
    metric, gained}`` dicts. Returns the number of newly inserted rows.
    """
    if not rows:
        return 0

    resolved_path = init_database(db_path)
    inserted = 0
    with closing(connect_db(resolved_path)) as conn:
        for row in rows:
            if not row.get("username"):
                continue
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO gains_history
                    (snapshot_time, period_start, period_end, username, metric, gained)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("snapshot_time"),
                    row.get("period_start"),
                    row.get("period_end"),
                    str(row.get("username")),
                    str(row.get("metric")),
                    float(row.get("gained", 0)),
                ),
            )
            inserted += cursor.rowcount
        conn.commit()
    return inserted


def list_gains_metrics(db_path: str | None = None) -> list[str]:
    """Return the distinct metrics that have stored gains snapshots."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        rows = conn.execute(
            "SELECT DISTINCT metric FROM gains_history ORDER BY metric"
        ).fetchall()
    return [row["metric"] for row in rows]


def read_gains_history(username: str, metric: str, db_path: str | None = None) -> list[dict]:
    """Return ``[{snapshot_time, gained}]`` for a player+metric, ordered by time."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        rows = conn.execute(
            """
            SELECT snapshot_time, gained FROM gains_history
            WHERE username = ? COLLATE NOCASE AND metric = ?
            ORDER BY snapshot_time
            """,
            (username, metric),
        ).fetchall()
    return [{"timestamp": row["snapshot_time"], "gained": row["gained"]} for row in rows]


def read_latest_gains(metric: str, limit: int = 20, db_path: str | None = None) -> list[dict]:
    """Return the most recent snapshot's leaderboard for ``metric`` (gained desc)."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        latest = conn.execute(
            "SELECT MAX(snapshot_time) AS ts FROM gains_history WHERE metric = ?",
            (metric,),
        ).fetchone()
        if not latest or latest["ts"] is None:
            return []
        rows = conn.execute(
            """
            SELECT username, gained, snapshot_time, period_start, period_end
            FROM gains_history
            WHERE metric = ? AND snapshot_time = ?
            ORDER BY gained DESC, username
            LIMIT ?
            """,
            (metric, latest["ts"], limit),
        ).fetchall()
    return [dict(row) for row in rows]


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


# ---------------------------------------------------------------------------
# Outbound WOM API call audit log (see utils.api_usage)
# ---------------------------------------------------------------------------


def log_api_call(
    *,
    method: str,
    endpoint: str,
    status_code: int | None,
    duration_ms: int | None,
    outcome: str,
    user_agent: str | None = None,
    timestamp: str | None = None,
    db_path: str | None = None,
) -> None:
    """Insert one row into the outbound API call audit log."""
    resolved_path = init_database(db_path)
    recorded_at = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with closing(connect_db(resolved_path)) as conn:
        conn.execute(
            """
            INSERT INTO api_call_log (timestamp, method, endpoint, status_code, duration_ms, outcome, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (recorded_at, method, endpoint, status_code, duration_ms, outcome, user_agent),
        )
        conn.commit()


def read_recent_api_calls(limit: int = 50, db_path: str | None = None) -> list[dict]:
    """Return the most recent API call log rows, newest first."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        rows = conn.execute(
            """
            SELECT timestamp, method, endpoint, status_code, duration_ms, outcome, user_agent
            FROM api_call_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def count_api_calls_since(since_timestamp: str, db_path: str | None = None) -> int:
    """Return the number of API calls logged at or after ``since_timestamp``."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM api_call_log WHERE timestamp >= ?",
            (since_timestamp,),
        ).fetchone()
    return int(row["count"]) if row else 0


def read_api_call_counts_by_endpoint(since_timestamp: str, db_path: str | None = None) -> list[dict]:
    """Return ``[{endpoint, count}]`` for calls at/after ``since_timestamp``, busiest first."""
    resolved_path = init_database(db_path)
    with closing(connect_db(resolved_path)) as conn:
        rows = conn.execute(
            """
            SELECT endpoint, COUNT(*) AS count
            FROM api_call_log
            WHERE timestamp >= ?
            GROUP BY endpoint
            ORDER BY count DESC
            """,
            (since_timestamp,),
        ).fetchall()
    return [dict(row) for row in rows]
