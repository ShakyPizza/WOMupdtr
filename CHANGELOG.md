# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-08-01

### Fixed
- **Unbounded pagination loop causing WOM API IP-block incidents.** `_get_group_gains()` in `weeklyupdater/weekly_reporter.py` (also used by `monthly_reporter.py`) paginated the WOM `groups/{id}/gains` endpoint using an `offset` parameter, but that endpoint ignores `offset` and always returns the full member list. For groups over 50 members, the loop's exit condition was never satisfied, so it ran unbounded with no backoff. This is the root cause of the request-storm incidents on 2026-07-23 (~4.5k requests) and 2026-07-25 (~14k requests in 9 hours) that got the server's IP blocked by WOM. Fixed to make a single request, matching the equivalent fix already applied to `gainstracker/gains_snapshotter.py` on 2026-07-23.
- `tests/conftest.py`'s fake WOM client previously mimicked *correct* pagination behavior (honoring `offset`), which is why no test caught the bug above. It now matches the real API by ignoring `offset`/`limit` and always returning the full list. Added a regression test asserting a single request is made regardless of group size.
- Outbound API endpoint classification (`utils/api_usage.py`) mislabeled every `groups.get_gains` call as `"other"` in the audit log, because the real WOM route is `/groups/{id}/gained`, not `/gains`. Classification is now a generic path normalizer instead of a hand-maintained (and incorrect) pattern list, so a future endpoint can't silently disappear into `"other"` the same way.
- `WOM.py`: guarded the EHP rank-up path against a theoretical `None` value before calling `log_ehp_history()`.
- Local `config.ini` (untracked, not in git) had a duplicate `track_ehp` key that would crash the bot at startup with `configparser.DuplicateOptionError`. Removed the duplicate.

### Added
- **Outbound API usage tracking and circuit breaker** (`utils/api_usage.py`). Every outbound call to the WOM API — whether made through the `wom_client` library or a raw diagnostic/admin `aiohttp` session — now goes through a single tracked session (`create_tracked_session`) that classifies, times, and logs it.
  - A rolling per-minute request counter trips a circuit breaker that blocks further outbound calls for a cooldown period if the rate is exceeded, so a future runaway loop is stopped automatically instead of running until someone notices an IP block. New config keys: `api_rate_limit_per_minute` (default `30`), `api_circuit_breaker_cooldown_seconds` (default `300`).
  - New `api_call_log` SQLite table recording every call: method, endpoint, status code, duration, outcome, and the exact user agent sent.
  - New "WOM API usage" panel on the admin dashboard showing live circuit-breaker state, calls in the last minute/hour/24h, and a table of recent calls.
  - Every real call is also printed to the console and the live log viewer, not just persisted to SQLite.
- `REPORTS_ENABLED` kill switch in `WOM.py`: a single flag that, when `False`, disables the weekly/monthly/yearly scheduled report tasks, their slash commands (`/weeklyupdate`, `/monthlyreport`, `/yearlyreport`, `/yearlyreportfile`), and the web dashboard's Reports tab together. Currently set to `False` pending confidence in the pagination fix above.

### Changed
- The WOM API `User-Agent` string now identifies the project with a version and repo link (`WOM-Updater/1.0 (https://github.com/ShakyPizza/WOMupdtr)`) instead of a bare handle, so the WOM team can identify and reach out about this bot directly.

## [1.0.0] - 2026-03-18
Initial tagged release. Change history prior to this file is available via `git log`.
