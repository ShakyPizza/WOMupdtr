# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this project is

WOMupdtr is a Discord bot + FastAPI web dashboard for a Wise Old Man (OSRS) group. It tracks EHB-based bossing ranks, optionally tracks EHP-based skilling ranks, records configurable gains snapshots, announces rank changes, and generates weekly/yearly reports.

## Commands

```bash
# Install dependencies
pip install -r python/requirements.txt

# Run the bot (headless unless web.enabled is true)
python python/WOM.py

# Run with Docker (web dashboard at http://localhost:8080)
docker compose up --build

# Run the full test suite
pytest

# Run focused rank/gains tests
pytest tests/test_rank_utils.py tests/test_rank_utils_ehp.py tests/test_gains_snapshotter.py
```

## Architecture

The bot (`python/WOM.py`) is the entry point. It:

1. Initializes SQLite, imports legacy EHB CSV history when needed, and starts the WOM and Discord clients.
2. Launches the rank check loop (`check_interval`, default 3600s), group refresh (every 48h), gains snapshotter, weekly reporter (Sundays 6pm UTC), and yearly reporter (Jan 1 noon UTC).
3. Optionally starts FastAPI when `[web] enabled = true` in `config.ini`.

Shared bot/web state lives in `python/web/services/bot_state.py` (`BotState`). This now includes `last_gains_snapshot` in addition to the existing task status and callbacks.

### Rank tracking loop (`WOM.py: check_for_rank_changes`)

1. Fetch group member details from WOM.
2. Calculate EHB rank from `[Group Ranking]`; when `track_ehp = true`, calculate EHP rank from `[Skilling Ranking]`.
3. Use `rank_utils.compute_member_update()` to evaluate EHB and EHP independently and merge them without discarding other per-player fields.
4. On EHB increase, notify Discord, append to the legacy EHB CSV when enabled, and update JSON/SQLite.
5. On EHP increase, notify Discord with an EHP label and append to SQLite `ehp_history`.

`python/player_ranks.json` remains the rank snapshot used by the bot and web UI. Entries always contain `last_ehb` and `rank`; EHP-enabled entries also contain `last_ehp` and `ehp_rank`. `save_ranks()` mirrors changed snapshots into SQLite while preserving optional/future fields. Manual `/update` changes only the EHB fields.

### Gains tracking

`python/gainstracker/gains_snapshotter.py` handles two related paths:

- The background snapshotter fetches every configured WOM metric over a trailing window, paginates groups larger than 50, and writes the complete multi-metric snapshot atomically to SQLite `gains_history`. Invalid metrics are skipped, but a snapshot with no valid metrics fails; WOM page failures abort the snapshot so partial data is not persisted.
- `/gains <metric> [days]` queries WOM live and returns a current leaderboard. It does not read the persisted snapshots.

The scheduler runs immediately and then every `gains_snapshot_interval` seconds (minimum sleep 60s). It optionally posts the first configured metric's latest leaderboard to `gains_channel_id`; channel `0` still permits SQLite collection.

### Official OSRS hiscores fallback reference

If Wise Old Man is unavailable, an individual player's raw hiscores can be fetched from the official OSRS JSON endpoint:

`https://secure.runescape.com/m=hiscore_oldschool/index_lite.json?player={player}`

URL-encode the player name before substituting it. The response contains `skills` (`rank`, `level`, and `xp`) and `activities` (`rank` and `score`, including boss kill counts). This is a fallback reference only and is not currently wired into the bot. It cannot replace WOM group endpoints or WOM-computed values such as EHB and EHP.

### Persistence and web dashboard

`python/utils/database.py` owns SQLite initialization and idempotent schema upgrades. The database path defaults to `python/database.db` and can be overridden with `WOM_DATABASE_PATH`. Relevant tables are `players`, `ehb_history`, `ehp_history`, `boss_kills_history`, and `gains_history`.

The dashboard now exposes EHP and gains data:

- Player lists/details include EHP and skilling rank alongside the existing EHB data.
- `/charts/api/ehp-history?player=...` reads EHP history from SQLite.
- `/charts/api/gains-history?player=...&metric=...` reads persisted gains history from SQLite.
- The charts page renders individual EHB, EHP, and configurable-metric gains charts.

### Key modules

| Path | Purpose |
|---|---|
| `python/WOM.py` | Entry point, bot lifecycle, rank checks, and periodic task startup |
| `python/utils/commands.py` | Discord slash commands, including `/ehpladder` and live `/gains` |
| `python/utils/rank_utils.py` | Shared EHB/EHP threshold parsing, state merging, JSON persistence, and next-rank helpers |
| `python/utils/database.py` | SQLite schema/migrations and EHB, EHP, boss, gains, and player persistence |
| `python/gainstracker/` | WOM gains collection, formatting, persistence, and scheduler |
| `python/utils/log_csv.py` | Legacy append-only EHB CSV logging |
| `python/weeklyupdater/` | Weekly and yearly report generation + scheduling |
| `python/web/` | FastAPI routers, services, Jinja2 templates, and static assets |

## Configuration

- `python/config.ini` contains Discord/WOM credentials, channel IDs, feature flags, and intervals. New settings are `discord.gains_channel_id`, `settings.track_ehp`, `settings.gains_snapshot_interval`, `settings.gains_window_days`, and comma-separated `settings.gains_metrics`.
- `python/ranks.ini` must contain `[Group Ranking]` for EHB. When EHP tracking is enabled it should also contain `[Skilling Ranking]`; copy `python/ranks.ini.example` for both ladders.
- Gains defaults are a daily snapshot (`86400`) of a trailing 7-day window for `overall,ehb`. EHP tracking defaults off.
- Docker mounts `config.ini` and `ranks.ini` read-only. CSV history can be redirected with `EHB_LOG_PATH`; SQLite can be redirected with `WOM_DATABASE_PATH`.

## Testing notes

- `tests/conftest.py` stubs optional runtime integrations and isolates rank/database paths.
- `tests/test_rank_utils_ehp.py` covers dual EHB/EHP ranks, state preservation, missing sections, and next-rank behavior.
- `tests/test_gains_snapshotter.py` covers pagination, metric resolution, leaderboard formatting, API failures, and atomic snapshots.
- `tests/test_database.py` and `tests/test_web_routers.py` cover the new persistence and HTTP endpoints.

## Known technical debt (from `rmap.md`)

- `commands.py` still contains 20+ commands in one large `setup_commands()` function and should be split by category.
- `WOM.py:get_rank()` is now only a compatibility wrapper over `rank_utils.get_rank_for_value()`; callers can eventually use the shared helper directly.
- Global state (`bot_state`, task handles) in `WOM.py` could be moved into a class.
- A monthly channel setting exists, but a monthly reporter is not implemented.
