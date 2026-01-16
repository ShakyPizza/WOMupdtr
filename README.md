# WOMupdtr

A Discord bot that integrates with the Wise Old Man API to track EHB-based ranks, post updates to Discord, and generate scheduled clan reports.

## Highlights
- EHB rank tracking with automatic rank-up notifications.
- Slash-command interface (no prefix commands).
- Group refresh via Wise Old Man update-all, plus periodic refresh.
- Weekly and yearly report generation (auto-scheduled or on-demand).
- Optional Baserow sync whenever a player EHB changes.
- CSV logging with auto-bootstrap of ranks from `ehb_log.csv` when JSON storage is missing.
- GUI control panel for logs, rankings, fan links, CSV viewing, and config toggles.
- Docker support with persisted CSV logs.

## Requirements
- Python 3.11+ (recommended)
- A Discord bot token and a Wise Old Man group ID

## Install
1. Clone the repository:
   ```bash
   git clone https://github.com/ShakyPizza/WOMupdtr.git
   cd WOMupdtr
   ```
2. Install dependencies:
   ```bash
   pip install -r python/requirements.txt
   ```
3. Create `python/config.ini`:
   ```ini
   [discord]
   token = YOUR_DISCORD_TOKEN
   channel_id = 123456789012345678
   weekly_channel_id = 0
   yearly_channel_id = 0
   monthly_channel_id = 0

   [wiseoldman]
   group_id = 1234
   group_passcode =
   api_key =

   [baserow]
   br_token =

   [settings]
   check_interval = 3600
   run_at_startup = false
   print_to_csv = true
   print_csv_changes = true
   post_to_discord = true
   silent_mode = false
   debug = false
   ```

Notes:
- `weekly_channel_id` and `yearly_channel_id` enable scheduled report posts. Set to `0` to disable.
- `monthly_channel_id` is currently unused; keep it at `0` if you are not using it.
- `group_passcode` is only required for `/refreshgroup` (Wise Old Man update-all).
- `api_key` is optional but helps with Wise Old Man rate limits.
- Keep your token/API values out of Git history.

4. Create `python/ranks.ini` to define rank thresholds:
   ```ini
   [Group Ranking]
   0-10 = Goblin
   10-50 = Opal
   50-120 = Sapphire
   120-250 = Emerald
   250-400 = Red Topaz
   400-550 = Ruby
   550-750 = Diamond
   750-1000 = Dragonstone
   1000-1500 = Onyx
   1500+ = Zenyte
   ```

## Run
From the repo root:
```bash
# Headless bot
python python/WOM.py

# GUI control panel, please note this GUI is still a very much work in progress
python python/gui.py
```

## Slash Commands
General:
- `/commands` - Lists all available commands.
- `/refresh` - Posts current group rankings.
- `/lookup <username>` - Shows rank/EHB for a player.
- `/update <username>` - Updates rank/EHB for one player (case-insensitive).
- `/rankup <username>` - Shows next rank threshold.
- `/goodnight` - Sends a good night message.

Group management:
- `/refreshgroup` - Triggers a Wise Old Man update-all.
- `/forcecheck` - Runs the rank-change check immediately.

Subscriptions:
- `/link <username> <discord_name>` - Links a Discord user to a Wise Old Man username.
- `/subscribeall <discord_name>` - Subscribes a Discord user to all players.
- `/unsubscribeall <discord_name>` - Removes a Discord user from all subscriptions.

Reports:
- `/weeklyupdate` - Posts a weekly report to the configured weekly channel.
- `/yearlyreport [year]` - Posts a yearly report (defaults to last completed year).
- `/yearlyreportfile [year] [filename]` - Writes a yearly report to a local file.

Debug:
- `/debug_group` - Inspects the current group response.
- `/sendrankup_debug` - Sends a simulated rank-up message.

## Weekly and Yearly Reports
The report system summarizes group activity using Wise Old Man gains/achievements data:
- Weekly: top overall XP gainer, top 3 EHB gainers, top Sailing gainer, and recent achievements.
- Yearly: top overall XP, EHB, and EHP gainers, Sailing highlights, 99s, max total achievements, name changes, and group stats.

Reports can be scheduled automatically (when channel IDs are set) or run on demand via slash commands.

## Logging
- EHB changes are logged to `ehb_log.csv` (defaults to `python/ehb_log.csv`).
- Set `EHB_LOG_PATH` to override the CSV location (useful in Docker).
- `player_ranks.json` stores the latest rank snapshot and is auto-bootstrapped from the CSV if missing.

## Docker
Build and run:
```bash
docker compose up --build
```
The compose file mounts:
- `python/config.ini` and `python/ranks.ini` (read-only).
- `./data` for persisted CSV logs (`EHB_LOG_PATH=/app/data/ehb_log.csv`).

## Tests
```bash
pytest
```

## License
MIT. See `LICENSE`.
