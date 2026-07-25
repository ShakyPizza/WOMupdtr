# WOMupdtr

A Discord bot that integrates with the Wise Old Man API to track EHB-based ranks, post updates to Discord, and generate scheduled clan reports.

## Highlights
- EHB rank tracking with automatic rank-up notifications.
- Slash-command interface (no prefix commands).
- Group refresh via Wise Old Man update-all, plus periodic refresh.
- Weekly and yearly report generation (auto-scheduled or on-demand).
- Local SQLite storage bootstrapped automatically on startup.
- CSV logging with auto-bootstrap of ranks from `ehb_log.csv` when JSON storage is missing.
- FastAPI web dashboard (players, reports, charts, admin, group pages).
- Docker support with persisted CSV logs — runs bot + web dashboard on port 8080.

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
   gains_channel_id = 0

   [wiseoldman]
   group_id = 1234
   group_passcode =
   api_key =
   [settings]
   check_interval = 3600
   run_at_startup = false
   print_to_csv = true
   print_csv_changes = true
   post_to_discord = true
   silent_mode = false
   debug = false
   track_ehp = false
   gains_snapshot_interval = 86400
   gains_window_days = 7
   gains_metrics = overall,ehb

   [web]
   enabled = true
   host = 0.0.0.0
   port = 8080
   ```

Notes:
- `weekly_channel_id`, `monthly_channel_id`, and `yearly_channel_id` enable scheduled report posts. Set any channel to `0` to disable it. Monthly reports post at 12:00 UTC on the first day of each month.
- `group_passcode` is only required for `/refreshgroup` (Wise Old Man update-all).
- `api_key` is optional but helps with Wise Old Man rate limits.
- EHP collection is opt-in. Set `track_ehp = true` to populate EHP ranks and history.
- Gains snapshots default to a 7-day window collected daily. `gains_channel_id = 0` keeps the snapshots in SQLite without posting a Discord digest.
- The web dashboard is disabled unless `[web] enabled = true`. Use `host = 0.0.0.0` in Docker so the published port can reach it; Docker Compose binds that port to host loopback by default. For a direct local run that should only be reachable from the same machine, use `host = 127.0.0.1`.
- Keep your token/API values out of Git history.

4. Copy `python/ranks.ini.example` to `python/ranks.ini`, then adjust the rank thresholds if needed:
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

   [Skilling Ranking]
   0-100 = Novice
   100-500 = Apprentice
   500-1000 = Adept
   1000-1500 = Expert
   1500+ = Master
   ```

The skilling ladder is used for EHP when `track_ehp = true`.

## Run
From the repo root:
```bash
# Headless bot
python python/WOM.py
```

## Slash Commands
General:
- `/commands` - Lists all available commands.
- `/refresh` - Posts current group rankings.
- `/lookup <username>` - Shows locally stored rank, EHB, EHP, and total XP for a player.
- `/update <username>` - Updates rank/EHB for one player (case-insensitive).
- `/rankup <username>` - Shows next rank threshold.
- `/goodnight` - Sends a good night message.

Group management:
- `/refreshgroup` - Triggers a Wise Old Man update-all.
- `/forcecheck` - Runs the rank-change check immediately.

Reports:
- `/weeklyupdate` - Posts a weekly report to the configured weekly channel.
- `/yearlyreport [year]` - Posts a yearly report (defaults to last completed year).
- `/yearlyreportfile [year] [filename]` - Writes a yearly report to a local file.

Debug:
- `/debug_group` - Inspects the current group response.
- `/sendrankup_debug` - Sends a simulated rank-up message.

## Web Dashboard
When running via Docker, the web dashboard is available at `http://localhost:8080`. You can also start it manually alongside the bot. Pages:
- `/` — overview dashboard
- `/players` — full member list with EHB history and search
- `/group` — group totals, rank distribution, and rank thresholds
- `/reports` — weekly and yearly report views
- `/charts` — rank distribution plus EHB, EHP, and gains history charts
- `/admin` — settings editor, log viewer, and bot controls

## Weekly and Yearly Reports
The report system summarizes group activity using Wise Old Man gains/achievements data:
- Weekly: top overall XP gainer, top 3 EHB gainers, top Sailing gainer, and recent achievements.
- Yearly: top overall XP, EHB, and EHP gainers, Sailing highlights, 99s, max total achievements, name changes, and group stats.

Reports can be scheduled automatically (when channel IDs are set) or run on demand via slash commands.

## Logging
- EHB changes are logged to `ehb_log.csv` (defaults to `python/ehb_log.csv`).
- Set `EHB_LOG_PATH` to override the CSV location (useful in Docker).
- SQLite data is stored in `python/database.db` by default.
- Set `WOM_DATABASE_PATH` to override the SQLite location. In Docker this defaults to `/app/data/database.db`.
- `player_ranks.json` stores the latest rank snapshot and is auto-bootstrapped from the CSV if missing.

## Docker
Build and run:
```bash
docker compose up --build
```
The compose file mounts:
- `python/config.ini` and `python/ranks.ini` (read-only).
- `./data` for persisted CSV logs and SQLite data (`EHB_LOG_PATH=/app/data/ehb_log.csv`, `WOM_DATABASE_PATH=/app/data/database.db`).

## Tests
```bash
pytest
```

## License
MIT. See `LICENSE`.
