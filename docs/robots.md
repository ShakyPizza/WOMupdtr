# WOMupdtr Project Overview

## Core Components
- `python/WOM.py`: Discord bot entry point; coordinates Wise Old Man API calls, commands, and Discord events.
- `python/gui.py`: Tkinter desktop control panel that starts/stops the bot, exposes quick actions, and streams logs via a shared queue.
- `python/utils/`: Helper modules for rank persistence (`rank_utils.py`), CSV logging (`log_csv.py`), Discord command wiring (`commands.py`), and Baserow integrations (`baserow_connect.py`).

## Configuration & Data
- `python/config.ini`: Central configuration for Discord credentials, Wise Old Man group info, and runtime toggles (e.g., check interval, logging preferences).
- `python/ranks.ini`: Defines EHB thresholds mapped to rank names that drive promotions.
- `python/utils/player_ranks.json`: Cache of member rank data used to detect rank changes.

## Runtime Behavior
- Discord client initializes message intents and slash command support; background tasks refresh Wise Old Man group data.
- GUI launches the bot in a worker thread, relays status updates, and offers dialogs for player lookup, updates, and subscriptions (logic stubs marked for completion).
- Rank changes trigger Discord announcements and optional CSV logging; API refreshes can also post to Discord.

## Testing & Tooling
- `tests/`: Pytest-based suite (review `tests` directory for coverage, currently focused on utility modules).
- `requirements.txt`: Pins dependencies (aiohttp, discord.py, tkinter included with Python). Activate the local venv in `.venv` when running locally.

## Getting Started
1. Populate `python/config.ini` with valid Discord token, channel ID, and Wise Old Man group credentials.
2. Optionally adjust rank thresholds in `python/ranks.ini`.
3. Launch the GUI via `python -m python.gui` or run the bot headless with `python -m python.WOM`.
4. Monitor `ehb_log.csv` and GUI console for activity and errors.
