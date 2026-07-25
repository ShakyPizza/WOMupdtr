# Database Schema

WOMupdtr uses a local SQLite database for persistent player snapshots, EHB
history, stable WOM player identities, aliases, and achievement events.

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

In `docker-compose.yml`, `./data` is mounted to `/app/data`, so the database survives container rebuilds and restarts.

## Initialization

`python/WOM.py` calls `init_database()` during startup before the Discord bot and web server are started. The helper creates the database directory and tables if they are missing.

For existing databases, initialization idempotently adds a nullable
`total_xp INTEGER` column to `players`. Legacy rows remain valid with no
total-XP value until the next rank refresh.

The schema is defined in:

```text
python/utils/database.py
```

Startup also seeds SQLite from existing local state:

- `player_ranks.json` is loaded and written into `players`.
- `ehb_log.csv` is imported into `ehb_history`.
- Duplicate EHB history rows are skipped.

The achievement-retention tables are additive. Existing username-keyed rank
and history tables remain unchanged, while achievement writes use Wise Old
Man's stable numeric player ID. Initialization uses `CREATE TABLE IF NOT
EXISTS` and `CREATE INDEX IF NOT EXISTS`, so the migration is idempotent.

## Tables

### `players`

Stores the latest rank snapshot and total XP for each player.

```sql
CREATE TABLE IF NOT EXISTS players (
    username TEXT PRIMARY KEY,
    last_ehb REAL NOT NULL DEFAULT 0,
    rank TEXT NOT NULL DEFAULT 'Unknown',
    updated_at TEXT NOT NULL
);
```

Columns:

| Column | Type | Purpose |
|---|---|---|
| `username` | `TEXT PRIMARY KEY` | Wise Old Man display name. |
| `last_ehb` | `REAL NOT NULL DEFAULT 0` | Latest known Efficient Hours Bossed value. |
| `rank` | `TEXT NOT NULL DEFAULT 'Unknown'` | Rank name calculated from `python/ranks.ini`. |
| `updated_at` | `TEXT NOT NULL` | UTC timestamp for the latest SQLite snapshot write. |
| `total_xp` | `INTEGER` | Latest overall experience returned by Wise Old Man; nullable for legacy rows. |

Writes:

- `save_ranks()` writes changed rank and total-XP snapshots through `upsert_players()`.
- `WOM.py` also upserts the full JSON snapshot at startup.

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
```

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Internal row ID. |
| `timestamp` | `TEXT NOT NULL` | Timestamp from the EHB log event or imported CSV row. |
| `username` | `TEXT NOT NULL` | Wise Old Man display name. |
| `ehb` | `REAL NOT NULL` | EHB value at that timestamp. |

Constraint:

```sql
UNIQUE(timestamp, username, ehb)
```

This prevents duplicate rows when importing `ehb_log.csv` repeatedly.

Index:

```sql
CREATE INDEX IF NOT EXISTS idx_ehb_history_username_ts
ON ehb_history (username, timestamp);
```

This supports player history lookups ordered by timestamp.

Writes:

- `log_ehb_to_csv()` also inserts the same EHB event into `ehb_history`.
- `import_csv_history()` imports existing CSV history at startup.

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
Wise Old Man API
  -> WOM.py rank check loop
  -> player_ranks.json latest EHB/total-XP snapshot
  -> players table

Rank EHB increase
  -> ehb_log.csv append
  -> ehb_history table

Wise Old Man group achievements API
  -> existing weekly/monthly/yearly report fetches
  -> wom_players + player_aliases + achievements
  -> boss-KC, XP, and level milestone report sections
```

## Operational Notes

- SQLite is local-only; Baserow sync has been retired.
- `python/database.db` is the default for direct local runs.
- Docker should use `WOM_DATABASE_PATH=/app/data/database.db` with `./data:/app/data` mounted.
- The schema is created with `CREATE TABLE IF NOT EXISTS`, so startup is safe when the database already exists.
