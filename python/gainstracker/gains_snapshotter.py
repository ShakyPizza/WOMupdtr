"""Persisted gains-snapshot collector and scheduler (Feature 4).

Unlike ``ehb_history`` (written only on EHB increase, EHB-only, sparse), this
module stores dense trailing-window gains snapshots straight from the Wise Old
Man gains API so the dashboard can chart per-metric moving averages.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import typing as t

from wom import enums

from utils.database import log_gains_snapshot, read_latest_gains

_TS_FMT = "%Y-%m-%d %H:%M:%S"


def resolve_metric(name: str) -> t.Optional[enums.Metric]:
    """Resolve a metric name (e.g. ``"overall"``, ``"ehb"``) to a ``Metric`` enum."""
    if not name:
        return None
    candidate = name.strip().lower()
    for metric in enums.Metric:
        if getattr(metric, "value", metric) == candidate:
            return metric
    # Fall back to matching the enum member name (e.g. "Overall").
    for metric in enums.Metric:
        if metric.name.lower() == candidate.replace("_", ""):
            return metric
    return None


async def _collect_gains(
    wom_client,
    group_id: int,
    metric: enums.Metric,
    start_date: datetime,
    end_date: datetime,
) -> list:
    """Fetch all group gains in one request.

    WOM's group-gains endpoint does not support pagination and always returns the
    full member list. Supplying an offset is ignored by the API.
    """
    result = await wom_client.groups.get_gains(
        group_id,
        metric,
        start_date=start_date,
        end_date=end_date,
    )
    if not result.is_ok:
        error = result.unwrap_err()
        raise RuntimeError(f"Failed to fetch gains for metric '{metric.value}': {error}")
    return list(result.unwrap())


def _build_gains_rows(
    entries: list,
    *,
    snapshot_time: str,
    period_start: str,
    period_end: str,
    metric: str,
) -> list[dict]:
    """Turn gains API entries into persistable rows (pure)."""
    rows: list[dict] = []
    for entry in entries:
        name = getattr(getattr(entry, "player", None), "display_name", None)
        if not name:
            continue
        gained = getattr(getattr(entry, "data", None), "gained", 0) or 0
        rows.append(
            {
                "snapshot_time": snapshot_time,
                "period_start": period_start,
                "period_end": period_end,
                "username": name,
                "metric": metric,
                "gained": float(gained),
            }
        )
    return rows


async def snapshot_gains_once(
    *,
    wom_client,
    group_id: int,
    metrics: list[str],
    window_days: int,
    log,
    now: t.Optional[datetime] = None,
) -> int:
    """Fetch and persist a trailing-window gains snapshot for each metric.

    Returns the number of newly inserted rows across all metrics.
    """
    now = now or datetime.now(timezone.utc)
    period_start = now - timedelta(days=window_days)
    snapshot_str = now.strftime(_TS_FMT)
    start_str = period_start.strftime(_TS_FMT)

    all_rows: list[dict] = []
    valid_metrics = 0
    for metric_name in metrics:
        metric = resolve_metric(metric_name)
        if metric is None:
            log(f"Gains snapshot: unknown metric '{metric_name}', skipping.")
            continue
        valid_metrics += 1
        entries = await _collect_gains(wom_client, group_id, metric, period_start, now)
        all_rows.extend(
            _build_gains_rows(
                entries,
                snapshot_time=snapshot_str,
                period_start=start_str,
                period_end=snapshot_str,
                metric=metric.value,
            )
        )

    if valid_metrics == 0:
        raise ValueError("Gains snapshot has no valid metrics configured.")

    return log_gains_snapshot(all_rows)


async def collect_gains_leaderboard(
    *,
    wom_client,
    group_id: int,
    metric_name: str,
    window_days: int,
    log,
    now: t.Optional[datetime] = None,
    limit: int = 15,
) -> list[tuple[str, float]]:
    """Compute a live (unpersisted) gains leaderboard for the ``/gains`` command."""
    metric = resolve_metric(metric_name)
    if metric is None:
        return []
    now = now or datetime.now(timezone.utc)
    period_start = now - timedelta(days=window_days)
    entries = await _collect_gains(wom_client, group_id, metric, period_start, now)
    ranked = [
        (getattr(entry.player, "display_name", "Unknown"), float(getattr(entry.data, "gained", 0) or 0))
        for entry in entries
    ]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[:limit]


def build_gains_lines(metric_name: str, window_days: int, leaderboard: list[tuple[str, float]]) -> list[str]:
    """Render a gains leaderboard as code-block table lines (pure)."""
    header = f"Top {metric_name} gains (last {window_days}d)"
    lines = [header, f"{'#':<4}{'Player':<20}{'Gained':<15}", "-" * 40]
    if not leaderboard:
        lines.append("No gains data available.")
        return lines
    for index, (name, gained) in enumerate(leaderboard, start=1):
        lines.append(f"{index:<4}{name:<20}{gained:>12,.0f}")
    return lines


async def _gains_snapshot_loop(
    *,
    wom_client,
    discord_client,
    group_id: int,
    channel_id: int,
    metrics: list[str],
    window_days: int,
    interval_seconds: int,
    initial_delay_seconds: int = 0,
    log,
    on_snapshot=None,
    debug: bool = False,
) -> None:
    if initial_delay_seconds > 0:
        await asyncio.sleep(initial_delay_seconds)

    while True:
        try:
            inserted = await snapshot_gains_once(
                wom_client=wom_client,
                group_id=group_id,
                metrics=metrics,
                window_days=window_days,
                log=log,
            )
            if debug:
                log(f"Gains snapshot stored {inserted} rows.")
            if on_snapshot is not None:
                on_snapshot()

            if channel_id and metrics:
                primary = metrics[0]
                leaderboard = [
                    (row["username"], row["gained"]) for row in read_latest_gains(primary, limit=15)
                ]
                lines = build_gains_lines(primary, window_days, leaderboard)
                channel = discord_client.get_channel(channel_id)
                if channel is not None:
                    await channel.send("```\n" + "\n".join(lines) + "\n```")  # pyright: ignore[reportAttributeAccessIssue]
        except Exception as e:  # noqa: BLE001 — a scheduler must not die on one bad cycle
            log(f"Gains snapshot loop error: {e}")

        await asyncio.sleep(max(interval_seconds, 60))


def start_gains_snapshotter(
    *,
    wom_client,
    discord_client,
    group_id: int,
    channel_id: int,
    metrics: list[str],
    window_days: int,
    interval_seconds: int,
    initial_delay_seconds: int = 0,
    log,
    on_snapshot=None,
    debug: bool = False,
) -> asyncio.Task:
    """Start the daily gains-snapshot task (persists + optional Discord digest)."""
    return asyncio.create_task(
        _gains_snapshot_loop(
            wom_client=wom_client,
            discord_client=discord_client,
            group_id=group_id,
            channel_id=channel_id,
            metrics=metrics,
            window_days=window_days,
            interval_seconds=interval_seconds,
            initial_delay_seconds=initial_delay_seconds,
            log=log,
            on_snapshot=on_snapshot,
            debug=debug,
        )
    )
