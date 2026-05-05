# WOMupdtr Refactor Roadmap

A reference document for a repo-wide refactor. Use this as a living guide — check off phases as you go.

---

## Project Overview

**What it is**: A Discord bot + FastAPI web dashboard for tracking EHB (Efficient Hours Bossed) based ranks for a Wise Old Man OSRS group.

**Entry points**:
- `python/WOM.py` — headless Discord bot (primary)
- Docker: `docker compose up --build` (runs bot + web, port 8080)

**Tech stack**: discord.py, wom.py, aiohttp, FastAPI, Uvicorn, Jinja2, SQLite, pytest

**Data stores**: `player_ranks.json` (local JSON), `ehb_log.csv` (append-only log), `database.db` (local SQLite)

---

## Key Functions Catalog

### `python/WOM.py` (473 lines) — Main bot entry point

| Function / Class | Signature | Purpose |
|---|---|---|
| `Client` | `class Client(wom.Client)` | Wraps wom.py client; manages aiohttp session lifecycle |
| `log` | `log(message: str)` | Timestamped print + optional GUI queue push |
| `get_rank` | `get_rank(ehb, ranks_file)` | **DUPLICATE** — same logic as `rank_utils._get_rank_for_ehb()`. Delete this. |
| `on_ready` | Discord event | Syncs slash commands, starts WOM session, spawns all background tasks |
| `check_for_rank_changes` | `@tasks.loop` async | Core loop: fetch WOM group → compare EHB → log CSV → update JSON → post Discord |
| `list_all_members_and_ranks` | `async def` | Fetch all members, format ranked table, chunk to Discord 2000-char limit |
| `refresh_group_data` | `async def` | POST to WOM update-all API with passcode; handles 200/401/429 responses |
| `refresh_group_task` | `@tasks.loop` async | Periodic group refresh (default every 172800s / 48h) |
| `send_rank_up_message` | `async def(username, new_rank, old_rank, ehb)` | Posts rank-up message to Discord |

**Key globals** (these are the problem):
- `bot_state` — `BotState` dataclass injected into web server
- `weekly_report_task`, `yearly_report_task` — task handles stored as globals

---

### `python/utils/rank_utils.py`

| Function | Signature | Purpose |
|---|---|---|
| `_bootstrap_ranks_from_csv` | `() -> None` | Seeds `player_ranks.json` from `ehb_log.csv` when JSON is missing |
| `load_ranks` | `() -> dict` | Reads the latest rank snapshot JSON |
| `save_ranks` | `(data: dict) -> None` | Writes JSON; syncs changed player snapshot rows to SQLite |
| `next_rank` | `(username: str) -> str` | Returns formatted "Rank at X EHB" progress string |
| `_get_rank_for_ehb` | `(ehb: float) -> str` | Parses `ranks.ini`, returns rank name — **re-reads file every call** (no cache) |

---

### `python/utils/log_csv.py`

| Function | Signature | Purpose |
|---|---|---|
| `_resolve_csv_path` | `(file_name: str) -> str` | Resolves absolute path; respects `EHB_LOG_PATH` env var |
| `log_ehb_to_csv` | `(username, ehb, file_name, print_csv_changes)` | Appends `[timestamp, username, ehb]` row |
| `load_latest_ehb_from_csv` | `(file_name) -> dict[str, float]` | Returns latest EHB per player (last occurrence wins) |

> This file is the cleanest in the codebase — minimal changes needed.

---

### `python/utils/commands.py` (540+ lines in one function)

All 20+ Discord slash commands defined inside a single `setup_commands(bot, ...)` function.

| Command | Handler summary |
|---|---|
| `/lookup <username>` | Show rank and EHB for a player |
| `/refresh` | Refresh and post full rankings table |
| `/forcecheck` | Manually trigger rank change detection |
| `/update <username>` | Update rank for one player (case-insensitive) |
| `/rankup <username>` | Show current rank + next threshold |
| `/refreshgroup` | Trigger WOM update-all API |
| `/weeklyupdate` | Post weekly report to configured channel |
| `/yearlyreport [year]` | Post yearly report |
| `/yearlyreportfile [year] [filename]` | Write yearly report to file |
| `/commands` | List all commands |
| `/goodnight` | Fun message |
| `/debug_group` | Inspect raw group API response |
| `/sendrankup_debug` | Simulate a rank-up message |

---

### `python/utils/database.py`

| Function | Signature | Purpose |
|---|---|---|
| `init_database` | `(db_path: str | None = None) -> str` | Creates the SQLite database and required tables |
| `upsert_players` | `(players: dict, db_path: str | None = None) -> None` | Updates latest player snapshot rows |
| `log_ehb_history` | `(username, ehb, timestamp, db_path) -> None` | Appends EHB history into SQLite |
| `import_csv_history` | `(db_path, file_name) -> int` | Imports existing CSV history into SQLite |

---

### `python/web/services/bot_state.py`

```python
@dataclass
class BotState:
    # Clients
    wom_client, discord_client
    # Config
    group_id, group_passcode, check_interval, post_to_discord, silent, debug
    # Callbacks (functions passed in from bot)
    get_rank, list_all_members_and_ranks, check_for_rank_changes, refresh_group_data, log_func
    # Telemetry
    log_buffer: deque  # max 500 entries
    last_rank_check, last_group_refresh, bot_started_at: datetime
```

---

### `python/web/services/ranks_service.py`

| Function | Returns | Purpose |
|---|---|---|
| `get_all_players_sorted` | `List[dict]` | All players sorted by EHB descending |
| `get_player_detail` | `dict` | Single player lookup (case-insensitive) |
| `get_rank_distribution` | `Dict[str, int]` | Rank name → count histogram |
| `search_players` | `List[dict]` | Prefix search on username |
| `get_rank_thresholds` | `List[dict]` | All rank bands with lower/upper/name |

---

### `python/web/services/csv_service.py`

| Function | Returns | Purpose |
|---|---|---|
| `get_player_ehb_history` | `List[dict]` | All EHB timestamps for one player |
| `get_recent_changes` | `List[dict]` | Most recent N EHB changes across all players |
| `get_all_ehb_entries` | `Dict[str, List]` | All CSV data grouped by player |

---

### `python/web/routers/`

| Router | Prefix | Key endpoints |
|---|---|---|
| `dashboard.py` | `/` | GET `/` → dashboard.html |
| `players.py` | `/players` | List, detail, search, EHB history |
| `reports.py` | `/reports` | Weekly/yearly report views |
| `charts.py` | `/charts` | EHB trend, rank distribution charts |
| `admin.py` | `/admin` | Settings editor, log viewer, bot controls |
| `group.py` | `/group` | Group stats, member list |

> Every router constructs `Jinja2Templates(directory=os.path.join(..., "templates"))` identically. See issue below.

---

### `python/weeklyupdater/weekly_reporter.py`

| Function | Purpose |
|---|---|
| `_most_recent_sunday_1800_utc(now)` | Calculate last Sunday 18:00 UTC |
| `_next_sunday_1800_utc(now)` | Calculate next Sunday 18:00 UTC |
| `_format_int(value)` / `_format_float(value)` | Number formatting with commas |
| `_is_level_measure(measure)` / `_is_experience_measure(measure)` | Achievement type checks |
| `_is_skill_metric(metric)` / `_metric_label(metric)` | Skill metric helpers |
| `start_weekly_reporter(...)` | Schedule weekly report task |
| `generate_weekly_report_messages(...)` | Build Discord embed list |
| `send_weekly_report(...)` | Post to Discord channel |

---

### `python/weeklyupdater/yearly_reporter.py`

| Function | Purpose |
|---|---|
| `_year_boundary_1200_utc(year)` | Jan 1 12:00 UTC for a given year |
| `_most_recent_jan1_1200_utc(now)` | Last Jan 1 12:00 UTC |
| `_next_jan1_1200_utc(now)` | Next Jan 1 12:00 UTC |
| `_get_group_member_map(wom_client, group_id, log)` | Fetch WOM member ID → name map |
| `start_yearly_reporter(...)` | Schedule yearly report task |
| `generate_yearly_report_messages(...)` | Build Discord embed list |
| `send_yearly_report(...)` | Post to Discord channel |
| `write_yearly_report_file(...)` | Write report to text file |

---

## Dependency Graph

```
WOM.py (entry point)
  ├── utils.rank_utils      (load_ranks, save_ranks)
  ├── utils.log_csv         (log_ehb_to_csv)
  ├── utils.commands        (setup_commands)
  ├── weeklyupdater         (start_weekly_reporter, start_yearly_reporter)
  └── web.create_app        (FastAPI factory)
      ├── web.services.bot_state   (BotState dataclass)
      ├── web.services.ranks_service  → utils.rank_utils
      ├── web.services.csv_service    → utils.log_csv
      └── web.routers.*

utils.rank_utils
  ├── utils.database        (upsert_players)
  └── utils.log_csv         (load_latest_ehb_from_csv)

utils.commands
  ├── utils.rank_utils
  └── weeklyupdater
```

---

## Issues Found (with file:line references)

### 1. Duplicate Rank Calculation Logic

- `python/WOM.py:130–149` — `get_rank(ehb, ranks_file)` function
- `python/utils/rank_utils.py:14–29` — `_get_rank_for_ehb(ehb)` function

Both parse `ranks.ini` and return a rank name. The one in `WOM.py` should be deleted and all callers pointed to `rank_utils`.

---

### 2. God Module: `WOM.py`

`python/WOM.py` combines: logging helper, config loading, Discord client subclass, WOM client subclass, event handlers, background task loops, message formatting, file I/O, and web server startup. It should be decomposed (see Proposed Structure below).

---

### 3. Hardcoded Magic Values

| Location | Value | Should become |
|---|---|---|
| `python/WOM.py:301` | `2000` | `DISCORD_MAX_MESSAGE_LENGTH` constant |
| `python/WOM.py:326` | WOM API URL (hardcoded string) | Config or constant |
| `python/utils/commands.py:363` | Same WOM API URL | Same constant |

---

### 4. Config Path Resolved 3+ Different Ways

| File | Pattern |
|---|---|
| `python/WOM.py:81` | `os.path.dirname(os.path.abspath(__file__))` |
| `python/utils/rank_utils.py:14` | Similar multi-level dirname |

All three need to agree on where `config.ini` lives. Centralize with a single `ConfigManager` or a `config/loader.py` module.

---

### 5. Global State via `global` Keyword

`python/WOM.py:58–59, 165–166, 260, 358` — uses `global bot_state`, `global weekly_report_task`, `global yearly_report_task`.

This makes testing nearly impossible and creates implicit coupling. Pass state explicitly or use a dependency injection pattern already established in `web/dependencies.py`.

---

### 6. `setup_commands()` is 540+ Lines

`python/utils/commands.py:36–576` — all 20+ slash commands defined inline in one function. The function signature passes 10+ arguments to every inner command closure.

Split into logical groups: player commands, group commands, report commands.

---

### 7. `ranks.ini` Re-read on Every Rank Lookup

`python/utils/rank_utils.py:14` — `_get_rank_for_ehb()` calls `configparser.read()` every single invocation. With dozens of members checked every hour, this is unnecessary I/O.

Add a simple module-level cache: read once, store the parsed thresholds.

---

### 8. Template Path Duplicated in Every Router

Every file under `python/web/routers/` contains:
```python
Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"))
```
This should be a single constant in `web/templates_path.py` or `web/app.py`.

---

### 9. Bare `except Exception` Catches

| Location | Impact |
|---|---|
| `python/utils/commands.py:74–79` and throughout | Swallows system errors, hides bugs |
| `python/web/services/csv_service.py:30, 57, 84` | Returns empty list with no log |

Replace with specific exceptions (e.g., `aiohttp.ClientError`, `ValueError`, `KeyError`) and always log the exception.

---

### 10. Unused Imports

| File | Unused import |
|---|---|
| `python/utils/commands.py:9` | `import os` |

---

### 11. Repeated Timestamp Format

`datetime.now().strftime("%Y-%m-%d %H:%M:%S")` appears in:
- `python/WOM.py:55`
- `python/utils/log_csv.py:26`

Extract to a single `format_timestamp()` utility function.

---

### 13. `_format_int` / `_format_float` Duplicated

`python/weeklyupdater/weekly_reporter.py` and `python/weeklyupdater/yearly_reporter.py` both define identical `_format_int()` and `_format_float()` helpers. Extract to `utils/formatting.py`.

---

## Proposed File Structure

The current structure is mostly fine. The key changes are decomposing `WOM.py` and extracting shared concerns.

```
python/
├── config/
│   ├── __init__.py
│   ├── loader.py          # ConfigManager singleton — reads config.ini and ranks.ini once
│   └── constants.py       # DISCORD_MAX_MESSAGE_LENGTH = 2000
│                          # WOM_UPDATE_ALL_URL = "https://api.wiseoldman.net/v2/groups/{id}/update-all"
│                          # TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"
│
├── bot/                   # NEW — extracts from WOM.py
│   ├── __init__.py
│   ├── client.py          # Discord Client subclass + on_ready handler
│   ├── tasks.py           # check_for_rank_changes loop, refresh_group_task loop
│   ├── messaging.py       # send_rank_up_message, list_all_members_and_ranks
│   └── commands/          # NEW — splits commands.py
│       ├── __init__.py    # setup_commands() wires all groups
│       ├── player.py      # /lookup /update /rankup
│       ├── group.py       # /refresh /refreshgroup /forcecheck /debug_group
│       └── reports.py     # /weeklyupdate /yearlyreport /yearlyreportfile /commands /goodnight
│
├── utils/
│   ├── __init__.py
│   ├── rank_utils.py      # Keep — remove get_rank() duplicate, add ranks.ini cache
│   ├── log_csv.py         # Keep as-is (cleanest file in repo)
│   ├── database.py        # Local SQLite storage for snapshot + EHB history
│   └── formatting.py      # NEW — format_timestamp(), format_int(), format_float()
│
├── web/
│   ├── __init__.py
│   ├── app.py             # Keep — add TEMPLATES_DIR constant here
│   ├── dependencies.py    # Keep as-is
│   ├── routers/           # Keep — update each to import TEMPLATES_DIR from app.py
│   │   ├── admin.py
│   │   ├── charts.py
│   │   ├── dashboard.py
│   │   ├── group.py
│   │   ├── players.py
│   │   └── reports.py
│   ├── services/
│   │   ├── bot_state.py   # Consider splitting: BotConfig + BotTelemetry + ClientRefs
│   │   ├── csv_service.py
│   │   ├── ranks_service.py
│   │   └── report_service.py
│   ├── static/
│   └── templates/
│
├── weeklyupdater/
│   ├── __init__.py
│   ├── weekly_reporter.py  # Keep — remove _format_int/_format_float (use utils/formatting.py)
│   └── yearly_reporter.py  # Keep — remove _format_int/_format_float (use utils/formatting.py)
│
└── WOM.py                  # Becomes thin entry point: load config, create bot, start uvicorn
```

---

## Phased Refactor Plan

### Phase 1 — Foundations (do this first, everything else depends on it)

- [ ] Create `python/config/constants.py` with `DISCORD_MAX_MESSAGE_LENGTH`, `WOM_UPDATE_ALL_URL`, `TIMESTAMP_FMT`
- [ ] Create `python/config/loader.py` with a `ConfigManager` that reads `config.ini` and `ranks.ini` once and caches the result. All other files import from here.
- [ ] Update all callers of hardcoded magic values

### Phase 2 — Split `WOM.py`

- [ ] Create `python/bot/client.py` — move `Client(wom.Client)` class and `on_ready` handler
- [ ] Create `python/bot/tasks.py` — move `check_for_rank_changes` and `refresh_group_task`
- [ ] Create `python/bot/messaging.py` — move `send_rank_up_message` and `list_all_members_and_ranks`
- [ ] Delete `get_rank()` from `WOM.py` — use `rank_utils._get_rank_for_ehb()` instead
- [ ] `WOM.py` becomes: load config → create bot → start uvicorn (~60 lines)

### Phase 3 — Split `commands.py`

- [ ] Create `python/bot/commands/player.py` — player-related commands
- [ ] Create `python/bot/commands/group.py` — group-related commands
- [ ] Create `python/bot/commands/reports.py` — report commands + misc
- [ ] Create `python/bot/commands/__init__.py` with `setup_commands()` that registers all three groups

### Phase 4 — DRY Up Duplicates

- [ ] Create `python/utils/formatting.py` with `format_timestamp()`, `format_int()`, `format_float()`
- [ ] Remove duplicate `_format_int`/`_format_float` from `weekly_reporter.py` and `yearly_reporter.py`
- [ ] Add ranks.ini cache to `rank_utils._get_rank_for_ehb()` (module-level dict, populated once)
- [ ] Add a `TEMPLATES_DIR` constant to `web/app.py` and import it in all routers

### Phase 5 — Error Handling & Global State

- [ ] Replace all bare `except Exception` with specific exception types
- [ ] Always log caught exceptions (don't silently return `[]`)
- [ ] Remove `global` usage from `WOM.py` — pass state via function arguments or `BotState`

### Phase 6 — Cleanup

- [ ] Remove unused imports (`os` in commands.py)
- [ ] Remove duplicate `log()` / timestamp logic — use `utils/formatting.py`
- [ ] Rename `next_rank()` → `get_next_rank_message()` (returns a string, not a rank object)

---

## What NOT to Change

- `python/utils/log_csv.py` — already well-structured; leave it
- `python/web/services/bot_state.py` — `BotState` dataclass is fine for now; splitting is optional
- `python/weeklyupdater/` — overall structure is good; only remove duplicate formatters
- `tests/` — add tests as you refactor, don't delete existing ones
- Docker/CI setup — works fine, leave it

---

## Quick Reference: Where to Find Things

| "I want to change..." | Look in |
|---|---|
| How ranks are calculated | `python/utils/rank_utils.py` |
| How EHB is logged to CSV | `python/utils/log_csv.py` |
| Discord slash commands | `python/utils/commands.py` (pre-refactor) or `python/bot/commands/` (post-refactor) |
| How rank changes are detected | `python/WOM.py:check_for_rank_changes` (pre) or `python/bot/tasks.py` (post) |
| SQLite persistence logic | `python/utils/database.py` |
| Weekly/yearly report logic | `python/weeklyupdater/` |
| Web dashboard routes | `python/web/routers/` |
| Web dashboard data queries | `python/web/services/` |
| Bot config loading | `python/WOM.py:80–98` (pre) or `python/config/loader.py` (post) |
| Rank thresholds config | `python/ranks.ini` |
