# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this project is

WOMupdtr is a Discord bot + FastAPI web dashboard for tracking EHB (Efficient Hours Bossed) based ranks for a Wise Old Man (OSRS) group. It automatically detects rank changes, sends Discord notifications, generates weekly/yearly reports, and provides a web dashboard.

## Commands

```bash
# Install dependencies
pip install -r python/requirements.txt

# Run the bot (headless)
python python/WOM.py

# Run with Docker (web dashboard at http://localhost:8080)
docker compose up --build

# Run tests
pytest

# Run a single test file
pytest tests/test_rank_utils.py
```

## Architecture

The bot (`python/WOM.py`) is the entry point. It:
1. Starts the WOM API client and Discord client
2. Launches periodic tasks: rank check loop (`check_interval`, default 3600s), group refresh (every 48h), weekly reporter (Sundays 6pm UTC), yearly reporter (Jan 1 noon UTC) #Monthly reporter not done yet!
3. Optionally spawns a FastAPI web server (if `[web] enabled = true` in `config.ini`)

**Shared state** between the bot and web server lives in `python/web/services/bot_state.py` (`BotState` dataclass).

### Core rank tracking loop (`WOM.py: check_for_rank_changes`)
1. Fetch group member details from WOM API
2. Compare each member's current EHB against `python/player_ranks.json`
3. On EHB increase: send Discord notification, append to `ehb_log.csv`, update JSON, optionally sync to Baserow

### Key modules
| Path | Purpose |
|---|---|
| `python/WOM.py` | Entry point, rank check loop, periodic tasks |
| `python/utils/commands.py` | All 20+ slash commands (large file, needs splitting) |
| `python/utils/rank_utils.py` | Load/save ranks, next rank threshold, Baserow sync |
| `python/utils/log_csv.py` | Append-only EHB CSV logging |
| `python/weeklyupdater/` | Weekly and yearly report generation + scheduling |
| `python/web/` | FastAPI app, routers, Jinja2 templates, static assets |
| `python/web/routers/` | One router per section: dashboard, players, reports, charts, admin, group |

### Configuration
- `python/config.ini` — Discord token, WOM group ID, channel IDs, feature flags (`post_to_discord`, `silent_mode`, `debug`, etc.)
- `python/ranks.ini` — EHB thresholds for 10 rank tiers (Goblin → Zenyte)
- Docker: `config.ini` and `ranks.ini` mounted read-only; CSV logs persisted via `./data` volume with `EHB_LOG_PATH=/app/data/ehb_log.csv`

### Known technical debt (from `rmap.md`)
- `commands.py` is 540+ lines in a single `setup_commands()` function — should be split by category
- `WOM.py` has a duplicate `get_rank()` that overlaps with `rank_utils._get_rank_for_ehb()
- Global state (`bot_state`, task handles) in `WOM.py` could be moved into a class
