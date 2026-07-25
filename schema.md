# Database Schema

WOMupdtr uses a local SQLite database for player snapshots, EHB and EHP
history, boss-kill snapshots, gains snapshots, stable WOM player identities,
aliases, and achievement events.

## Location

Default local path:

```text
python/database.db
```

Docker path:

```text
/app/data/database.db
```

The path can be overridden with:

```text
WOM_DATABASE_PATH=/path/to/database.db
```

In `docker-compose.yml`, `./data` is mounted to `/app/data`, so the database
survives container rebuilds and restarts.

## Initialization and Migration

`python/WOM.py` calls `init_database()` during startup before the Discord bot
and web server are started. The schema is defined in:

```text
python/utils/database.py
```

`init_database()` creates the database directory, application tables, and
indexes if they are missing. It also inspects an existing `players` table with
`PRAGMA table_info` and adds missing EHP, total-XP, and player-status columns
with `ALTER TABLE ... ADD COLUMN`. This migration is idempotent, and
interpolated table and column names are validated as SQL identifiers before
the DDL runs.

Startup also seeds SQLite from existing local state:

- `player_ranks.json` is loaded and written into `players`.
- `ehb_log.csv` is imported into `ehb_history`.
- Duplicate EHB history rows are skipped.

The achievement-retention tables are additive. Existing username-keyed rank
and history tables remain unchanged, while achievement writes use Wise Old
Man's stable numeric player ID. Initialization uses `CREATE TABLE IF NOT
EXISTS` and `CREATE INDEX IF NOT EXISTS`, so the migration is idempotent.

There is no startup import for EHP, boss-kill, or gains history.

## Tables

### `players`

Stores the latest EHB/EHP rank snapshot, total XP, and optional Wise Old Man
status/activity metadata for each player.

| Column | Type | Purpose |
|---|---|---|
| `username` | `TEXT PRIMARY KEY` | Wise Old Man display name. |
| `last_ehb` | `REAL NOT NULL DEFAULT 0` | Latest known Efficient Hours Bossed value. |
| `rank` | `TEXT NOT NULL DEFAULT 'Unknown'` | EHB rank calculated from `python/ranks.ini`. |
| `updated_at` | `TEXT NOT NULL` | UTC timestamp for the latest rank snapshot write. |
| `last_ehp` | `REAL NOT NULL DEFAULT 0` | Latest known Efficient Hours Played value. |
| `ehp_rank` | `TEXT NOT NULL DEFAULT 'Unknown'` | EHP rank calculated from `python/ranks.ini`. |
| `total_xp` | `INTEGER` | Latest overall experience returned by Wise Old Man. |
| `player_id` | `INTEGER` | Wise Old Man player ID, when captured. |
| `wom_status` | `TEXT` | Wise Old Man player status, when captured. |
| `last_changed_at` | `TEXT` | Wise Old Man last-change timestamp. |
| `wom_updated_at` | `TEXT` | Wise Old Man update timestamp. |
| `last_progressed_at` | `TEXT` | Latest known progress timestamp. |
| `status_captured_at` | `TEXT` | UTC timestamp when status metadata was captured. |

The first four columns are created by the base `CREATE TABLE` statement.
`init_database()` adds the remaining columns to both new and legacy databases
through the idempotent migration helper.

Writes:

- `save_ranks()` upserts rows whose EHB, EHP, total XP, or calculated rank changed.
- `WOM.py` upserts the full JSON snapshot at startup.
- `upsert_player_status()` can update only the status/activity fields without
  overwriting rank values. No current runtime flow calls it.

### `ehb_history`

Stores append-only EHB history entries.

```sql
CREATE TABLE IF NOT EXISTS ehb_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    username TEXT NOT NULL,
    ehb REAL NOT NULL,
    UNIQUE(timestamp, username, ehb)
);

CREATE INDEX IF NOT EXISTS idx_ehb_history_username_ts
ON ehb_history (username, timestamp);
```

`log_ehb_to_csv()` inserts the same event into this table after appending it to
the CSV. In the rank-check loop, this only happens when CSV logging is enabled
and EHB increased. `import_csv_history()` imports existing CSV rows at startup.
The unique key makes repeated imports idempotent.

### `ehp_history`

Stores append-only EHP history entries.

```sql
CREATE TABLE IF NOT EXISTS ehp_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    username TEXT NOT NULL,
    ehp REAL NOT NULL,
    UNIQUE(timestamp, username, ehp)
);

CREATE INDEX IF NOT EXISTS idx_ehp_history_username_ts
ON ehp_history (username, timestamp);
```

When `track_ehp` is enabled, the rank-check loop inserts an entry through
`log_ehp_history()` when a player's EHP increases. The unique key makes a
repeated event idempotent. The web dashboard reads a player's history ordered
by timestamp.

### `boss_kills_history`

Stores per-boss leaderboard snapshots.

```sql
CREATE TABLE IF NOT EXISTS boss_kills_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    boss TEXT NOT NULL,
    username TEXT NOT NULL,
    kills INTEGER NOT NULL,
    rank INTEGER,
    UNIQUE(timestamp, boss, username)
);

CREATE INDEX IF NOT EXISTS idx_boss_kills_boss_ts
ON boss_kills_history (boss, timestamp);
```

`log_boss_kills()` can insert a complete boss snapshot with duplicate rows
ignored. Database helpers can read the latest leaderboard, one player's
history for a boss, and the list of tracked bosses. No current runtime flow
calls the writer.

### `gains_history`

Stores trailing-window gains snapshots for configured Wise Old Man metrics.

```sql
CREATE TABLE IF NOT EXISTS gains_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    username TEXT NOT NULL,
    metric TEXT NOT NULL,
    gained REAL NOT NULL,
    UNIQUE(snapshot_time, username, metric)
);

CREATE INDEX IF NOT EXISTS idx_gains_metric_ts
ON gains_history (metric, snapshot_time);

CREATE INDEX IF NOT EXISTS idx_gains_user_metric_ts
ON gains_history (username, metric, snapshot_time);
```

The gains snapshot task fetches the full group result for each configured
metric, then persists one row per player and metric through
`log_gains_snapshot()`. `gains_snapshot_interval`, `gains_window_days`, and
`gains_metrics` control the scheduled collection. Duplicate snapshot rows are
ignored. The dashboard reads metric leaderboards and per-player histories;
the task can also post the latest primary-metric leaderboard to Discord.

## Relationships

The tables do not declare foreign keys. `username` is the logical link between
`players` and the four history tables. History remains valid even when a
player has no current row in `players`.

### `wom_players`

Stores useful identity/profile fields embedded in achievement API results. Raw
API payloads are not retained.

```sql
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
);
```

Rows are upserted by `player_id`. Missing optional fields in later responses do
not erase previously captured values.

### `player_aliases`

Tracks display names observed for each stable WOM player ID.

```sql
CREATE TABLE IF NOT EXISTS player_aliases (
    player_id INTEGER NOT NULL,
    normalized_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (player_id, normalized_name)
);
```

### `achievements`

Stores normalized achievement events already fetched for periodic reports.

```sql
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
);
```

The natural deduplication identity excludes display text and timestamps because
WOM may recalculate `achieved_at` and `accuracy_ms`. Repeated observations
update mutable event fields and `last_seen_at`.

## Data Flow

```text
Wise Old Man group details
  -> WOM.py rank check loop
  -> player_ranks.json latest EHB/EHP/total-XP snapshot
  -> players table

EHB increase, when CSV logging is enabled
  -> ehb_log.csv append
  -> ehb_history table

Wise Old Man group achievements API
  -> existing weekly/monthly/yearly report fetches
  -> wom_players + player_aliases + achievements
  -> boss-KC, XP, and level milestone report sections

EHP increase, when track_ehp is enabled
  -> ehp_history table

Wise Old Man group gains API
  -> scheduled trailing-window snapshots
  -> gains_history table
  -> dashboard charts and optional Discord digest

Boss/status database helpers
  -> boss_kills_history or players status columns
  (not currently called by a runtime collector)
```

## Operational Notes

- `python/database.db` is the default for direct local runs.
- Docker uses `WOM_DATABASE_PATH=/app/data/database.db` with
  `./data:/app/data` mounted.
- Table/index creation and the current column migration are safe to run
  repeatedly.
