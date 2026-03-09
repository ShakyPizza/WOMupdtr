# WOMupdtr Refactor Roadmap (`rmap.md`)

## 1) High-level map of the current codebase

This repo currently has **three runtime surfaces** sharing logic/state:

1. **Discord bot runtime** (`python/WOM.py`)  
   - Owns startup, config loading, scheduled tasks, rank checks, Discord posting, and command registration.
2. **Tkinter desktop GUI** (`python/gui.py`)  
   - Starts/stops bot from a thread, shows rankings/logs, and edits config.
3. **FastAPI web dashboard** (`python/web/*`)  
   - Reads rank + CSV data through service wrappers and exposes views/APIs.

Supporting domains:
- **Persistence + integration** (`python/utils/*`): JSON rank state, CSV logs, Baserow sync, Discord command definitions.
- **Reporting** (`python/weeklyupdater/*`): weekly/yearly data collection, summarization, scheduling, and output chunking.
- **Tests** focus mostly on rank utils and CSV logging (`tests/*`).

---

## 2) Key functions and why they matter

## A. Entrypoint & orchestration (`python/WOM.py`)

- `Client.start()` / `Client.close()`  
  Critical lifecycle wrapper around WOM client + aiohttp session management. Good candidate for extraction into `infrastructure/wom_client.py`.

- `log(message)`  
  Shared logging fan-out (console + GUI queue + bot state buffer). It is used as a de facto cross-interface event bus.

- `get_rank(ehb, ranks_file=...)`  
  Core business rule for rank assignment from thresholds. **Duplicated concept** also exists in `utils.rank_utils._get_rank_for_ehb`.

- `on_ready()`  
  Giant startup coordinator: sync commands, start client sessions, schedule weekly/yearly tasks, run startup sync, and start loops.

- `check_for_rank_changes()`  
  Main periodic workflow (fetch members, compare old/new EHB, post rank-up, log CSV, save). This is one of the most important refactor targets.

- `list_all_members_and_ranks()`  
  Fetches + formats group standings and posts chunked Discord messages.

- `refresh_group_data()` / `refresh_group_task()`  
  Handles group refresh endpoint and optional Discord status posting.

- `send_rank_up_message()`  
  Side-effect function joining persistence (`load_ranks`) and Discord messaging.

## B. Rank persistence and derived rank logic (`python/utils/rank_utils.py`)

- `_get_rank_for_ehb(ehb)`  
  Rank threshold engine for bootstrap path. Should become the single shared rank resolver used by all interfaces.

- `_bootstrap_ranks_from_csv()`  
  Recovery path that seeds JSON state from CSV when JSON missing/corrupt.

- `load_ranks()` / `save_ranks(data)`  
  Core state IO. `save_ranks` also triggers Baserow sync side effects if EHB changed.

- `next_rank(username)`  
  Domain helper used in slash commands and web UI.

## C. CSV history (`python/utils/log_csv.py`)

- `_resolve_csv_path(file_name)`  
  Important portability function (local + Docker path behavior).

- `log_ehb_to_csv(...)` and `load_latest_ehb_from_csv(...)`  
  The append/read API for historical EHB records and bootstrap support.

## D. Command registration (`python/utils/commands.py`)

- `setup_commands(...)`  
  One very large function that registers all slash commands. It mixes command wiring, business logic, API calls, and formatting. This should be split by command domain modules.

- `format_discord_fans(...)`  
  Small presentational helper currently embedded with command registration.

## E. External sync (`python/utils/baserow_connect.py`)

- `post_to_ehb_table(...)` and `update_players_table(...)`  
  Integration boundary with Baserow. Currently tightly coupled to import-time config loading and hardcoded table IDs.

## F. Weekly/yearly reports (`python/weeklyupdater/*`)

- Weekly key public APIs:  
  `start_weekly_reporter`, `most_recent_week_end`, `generate_weekly_report_messages`, `send_weekly_report`.

- Yearly key public APIs:  
  `start_yearly_reporter`, `most_recent_year_end`, `generate_yearly_report_messages`, `send_yearly_report`, `write_yearly_report_file`.

- Internal report builders (both files):  
  `_get_group_member_map`, `_get_group_gains`, `_get_group_achievements`, `_build_report_lines`, `_chunk_messages`, and scheduling loops.  
  These are powerful and reusable but currently hidden in large modules with duplicated utility patterns between weekly/yearly.

## G. Web app entry + services (`python/web/*`)

- `create_app(state)` (`web/app.py`)  
  Clean app factory, good existing seam.

- Service functions in `web/services/ranks_service.py`:  
  `get_all_players_sorted`, `get_player_detail`, `get_rank_distribution`, `search_players`, `get_rank_thresholds`.

- Service functions in `web/services/csv_service.py`:  
  `get_player_ehb_history`, `get_recent_changes`, `get_all_ehb_entries`.

- Service functions in `web/services/report_service.py`:  
  `get_weekly_report`, `get_yearly_report`.

- Routers (`web/routers/*.py`) are thin and mostly okay; they should stay presentation-oriented.

## H. GUI (`python/gui.py`)

`BotGUI` is a very large god-class. Critical methods include:
- Lifecycle/control: `start_bot`, `stop_bot`, `run_bot`, `refresh_rankings`, `update_group`, `force_check`.
- Rendering/update: `create_sidebar`, `create_main_content`, `refresh_rankings_display`, `refresh_fans_display`, `check_queue`.
- Config + actions: `edit_config`, dialog methods, `link_user`.

This file is a prime extraction target for maintainability.

---

## 3) Major refactor pain points discovered

1. **Business logic duplication**  
   Rank threshold parsing exists in multiple places.

2. **Monolithic orchestrators**  
   `WOM.py`, `gui.py`, and `setup_commands` all contain too much mixed concern.

3. **Global mutable state + side effects**  
   Several modules execute config reads and integration assumptions at import time.

4. **Weak boundaries between domain and transport**  
   Discord/web/GUI logic often directly touches persistence and API clients.

5. **Testing coverage is narrow**  
   Good utility tests exist, but core orchestration/reporting/command behavior is under-tested.

---

## 4) Proposed new file structure (recommended)

A domain-first, interface-separated structure will make rebasing and incremental cleanup safer:

```text
python/
  app/
    config.py                  # typed settings loader
    logging.py                 # unified logger/event sink
    container.py               # dependency wiring

  domain/
    ranks/
      model.py                 # RankRule, PlayerRank
      service.py               # rank resolution + next-rank logic
      repository.py            # load/save player rank state
    history/
      csv_repository.py        # CSV append/read/query
    reports/
      weekly_service.py
      yearly_service.py
      shared.py                # chunking/format helpers

  integrations/
    wom_client.py              # WOM API wrappers
    discord_gateway.py         # Discord send/wrapper operations
    baserow_client.py          # Baserow operations

  interfaces/
    discord_bot/
      main.py                  # bot startup
      events.py                # on_ready, loop startup
      tasks.py                 # periodic checks/refresh
      commands/
        general.py
        players.py
        reports.py
        subscriptions.py
    web/
      app.py
      routers/
      services/
      templates/
      static/
    gui/
      app.py
      views/
      controllers/

  main.py                      # unified runtime entrypoint selector
```

### Notes on migration strategy
- Keep old paths as thin compatibility wrappers during transition.
- First extract pure functions (rank rules, formatting, chunking), then move orchestration.
- Avoid moving templates/static until back-end service seams are stable.

---

## 5) Suggested phased refactor plan

### Phase 1: Stabilize core domain
1. Create a single `rank service` and update all callers (`WOM.py`, `rank_utils.py`, web services).
2. Introduce a typed config/settings module; stop config reads at import time.
3. Extract CSV and JSON repositories behind clean interfaces.

### Phase 2: Split transport/interface layers
1. Break `setup_commands` into command modules by feature.
2. Extract Discord periodic workflows from `WOM.py` into `tasks` module.
3. Move Baserow logic behind a dedicated client with explicit enable/disable behavior.

### Phase 3: Reporting convergence
1. Pull shared report helpers into `reports/shared.py`.
2. Reduce duplicated logic between weekly/yearly reporters.
3. Add deterministic tests for report line building/chunking.

### Phase 4: GUI decomposition
1. Split `BotGUI` into view + controller modules.
2. Reuse domain services instead of importing bot globals directly.
3. Remove placeholder dialogs or wire them to real service calls.

### Phase 5: Test + safety net expansion
1. Add integration tests for rank-change detection workflow.
2. Add web service unit tests and router smoke tests.
3. Add command-handler tests with mocked Discord interactions.

---

## 6) Practical “start here” checklist

- [ ] Unify rank threshold logic into one module.
- [ ] Add `app/config.py` with validated settings and defaults.
- [ ] Extract `check_for_rank_changes` into a testable function that accepts dependencies.
- [ ] Split slash command definitions into multiple files.
- [ ] Introduce a `services` layer consumed by Discord + Web + GUI.
- [ ] Add tests for rank-check workflow and report formatting edge cases.

---

## 7) Final recommendation

If you are planning a repo-wide rebase, prioritize **seam creation before folder movement**:
- First make behavior-preserving extractions with compatibility imports.
- Then move files once tests cover the new seams.

This will reduce merge conflicts and make the rebase significantly safer.
