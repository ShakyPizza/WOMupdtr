# Database Schema

WOMupdtr uses a local SQLite database for persistent player snapshots and EHB history.

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

The schema is defined in:

```text
python/utils/database.py
```

Startup also seeds SQLite from existing local state:

- `player_ranks.json` is loaded and written into `players`.
- `ehb_log.csv` is imported into `ehb_history`.
- Duplicate EHB history rows are skipped.

## Tables

### `players`

Stores the latest rank snapshot for each player.

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

Writes:

- `save_ranks()` writes changed player snapshots through `upsert_players()`.
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

## Data Flow

```text
Wise Old Man API
  -> WOM.py rank check loop
  -> player_ranks.json latest snapshot
  -> players table

Rank EHB increase
  -> ehb_log.csv append
  -> ehb_history table
```

## Operational Notes

- SQLite is local-only; Baserow sync has been retired.
- `python/database.db` is the default for direct local runs.
- Docker should use `WOM_DATABASE_PATH=/app/data/database.db` with `./data:/app/data` mounted.
- The schema is created with `CREATE TABLE IF NOT EXISTS`, so startup is safe when the database already exists.
