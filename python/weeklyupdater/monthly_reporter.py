"""Monthly group report scheduler and data collector."""

from __future__ import annotations

import asyncio
import calendar
from datetime import datetime, timezone

from wom import enums

from .achievement_retention import (
    append_milestone_sections,
    categorize_additional_milestones,
    persist_fetched_achievements,
)
from .weekly_reporter import (
    _chunk_messages,
    _format_float,
    _format_int,
    _get_group_gains,
    _is_experience_measure,
    _is_level_measure,
    _is_skill_metric,
    _matches_threshold,
    _metric_label,
    _LEVEL_99_XP,
)


def _month_boundary_1800_utc(year: int, month: int) -> datetime:
    return datetime(year, month, 1, 18, 0, tzinfo=timezone.utc)


def _previous_month_boundary(boundary: datetime) -> datetime:
    if boundary.month == 1:
        return _month_boundary_1800_utc(boundary.year - 1, 12)
    return _month_boundary_1800_utc(boundary.year, boundary.month - 1)


def _most_recent_month_end(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    boundary = _month_boundary_1800_utc(now.year, now.month)
    if now < boundary:
        boundary = _previous_month_boundary(boundary)
    return boundary


def _next_month_end(now: datetime) -> datetime:
    boundary = _most_recent_month_end(now)
    if boundary.month == 12:
        return _month_boundary_1800_utc(boundary.year + 1, 1)
    return _month_boundary_1800_utc(boundary.year, boundary.month + 1)


async def _get_group_member_map(wom_client, group_id: int, log) -> dict[int, str]:
    result = await wom_client.groups.get_details(group_id)
    if not result.is_ok:
        log(f"Monthly report: failed to fetch group details: {result.unwrap_err()}")
        return {}
    group = result.unwrap()
    return {membership.player.id: membership.player.display_name for membership in group.memberships}


async def _get_dated_pages(
    fetch_page,
    *,
    start_date: datetime,
    end_date: datetime,
    log,
    label: str,
    limit: int = 50,
) -> list:
    entries = []
    offset = 0
    while True:
        result = await fetch_page(limit, offset)
        if not result.is_ok:
            log(f"Monthly report: failed to fetch {label}: {result.unwrap_err()}")
            break
        page = list(result.unwrap())
        if not page:
            break
        entries.extend(item for item in page if start_date <= item.created_at < end_date)
        if len(page) < limit or page[-1].created_at < start_date:
            break
        offset += limit
    return entries


def _build_report_lines(
    *,
    start_date: datetime,
    end_date: datetime,
    overall_gains: list,
    ehb_gains: list,
    ehp_gains: list,
    sailing_gains: list,
    name_changes: list,
    achievements: list,
    player_name_map: dict[int, str],
    boss_kc_achievements: list | None = None,
    xp_achievements: list | None = None,
    level_achievements: list | None = None,
) -> list[str]:
    month_label = f"{calendar.month_name[start_date.month]} {start_date.year}"
    lines = [
        f"Monthly Report - {month_label}",
        f"({start_date.strftime('%Y-%m-%d %H:%M')} UTC - {end_date.strftime('%Y-%m-%d %H:%M')} UTC)",
        "",
    ]

    total_xp = sum(entry.data.gained for entry in overall_gains)
    active_members = sum(1 for entry in overall_gains if entry.data.gained > 0)
    lines.extend(
        [
            "Month at a glance",
            f"- Group XP gained: {_format_int(total_xp)} xp",
            f"- Active gainers: {active_members}/{len(player_name_map)} members",
            f"- Group EHB gained: {_format_float(sum(entry.data.gained for entry in ehb_gains))}",
            f"- Group EHP gained: {_format_float(sum(entry.data.gained for entry in ehp_gains))}",
            f"- New 99s: {len(achievements)}",
            "",
        ]
    )

    metric_sections = (
        ("Top overall XP gainers", overall_gains, "xp", _format_int, 5),
        ("Top EHB gainers", ehb_gains, "EHB", _format_float, 5),
        ("Top EHP gainers", ehp_gains, "EHP", _format_float, 5),
        ("Top Sailing gainers", sailing_gains, "xp", _format_int, 3),
    )
    for title, gains, unit, formatter, count in metric_sections:
        if gains:
            lines.append(f"{title}:")
            for index, entry in enumerate(gains[:count], start=1):
                lines.append(
                    f"{index}. {entry.player.display_name} (+{formatter(entry.data.gained)} {unit})"
                )
        else:
            lines.append(f"{title}: no data")
        lines.append("")

    if achievements:
        lines.append("New 99s:")
        grouped: dict[str, list[str]] = {}
        for achievement in achievements:
            name = player_name_map.get(achievement.player_id, f"Player {achievement.player_id}")
            grouped.setdefault(name, []).append(_metric_label(achievement.metric))
        for name in sorted(grouped, key=str.casefold):
            lines.append(f"- {name}: {', '.join(grouped[name])}")
    else:
        lines.append("New 99s: none")

    append_milestone_sections(
        lines,
        boss_kc=boss_kc_achievements or [],
        xp=xp_achievements or [],
        level=level_achievements or [],
        player_name_map=player_name_map,
    )
    lines.append("")

    if name_changes:
        lines.append(f"Name changes: {len(name_changes)}")
        for change in name_changes[:10]:
            lines.append(
                f"- {change.old_name} -> {change.new_name} "
                f"({change.status.value}, {change.created_at.strftime('%Y-%m-%d')})"
            )
        if len(name_changes) > 10:
            lines.append(f"...and {len(name_changes) - 10} more name changes")
    else:
        lines.append("Name changes: none")

    return lines


async def _generate_monthly_report(*, wom_client, group_id: int, end_date: datetime, log) -> list[str]:
    start_date = _previous_month_boundary(end_date)
    player_name_map = await _get_group_member_map(wom_client, group_id, log)

    overall_gains = await _get_group_gains(
        wom_client, group_id, enums.Metric.Overall, start_date, end_date, limit=50
    )
    ehb_gains = await _get_group_gains(
        wom_client, group_id, enums.Metric.Ehb, start_date, end_date, limit=50
    )
    ehp_gains = await _get_group_gains(
        wom_client, group_id, enums.Metric.Ehp, start_date, end_date, limit=50
    )
    sailing_gains = await _get_group_gains(
        wom_client, group_id, enums.Metric.Sailing, start_date, end_date, limit=50
    )

    groups = wom_client.groups
    name_changes = await _get_dated_pages(
        lambda limit, offset: groups.get_name_changes(group_id, limit=limit, offset=offset),
        start_date=start_date,
        end_date=end_date,
        log=log,
        label="name changes",
    )
    raw_achievements = await _get_dated_pages(
        lambda limit, offset: groups.get_achievements(group_id, limit=limit, offset=offset),
        start_date=start_date,
        end_date=end_date,
        log=log,
        label="achievements",
    )
    persist_fetched_achievements(
        raw_achievements,
        group_id=group_id,
        player_name_map=player_name_map,
        log=log,
    )
    milestone_categories = categorize_additional_milestones(raw_achievements)
    achievements = [
        item
        for item in raw_achievements
        if _is_skill_metric(item.metric)
        and (
            (_is_level_measure(item.measure) and _matches_threshold(item.threshold, 99))
            or (_is_experience_measure(item.measure) and _matches_threshold(item.threshold, _LEVEL_99_XP))
        )
    ]

    for gains in (overall_gains, ehb_gains, ehp_gains, sailing_gains):
        gains.sort(key=lambda entry: entry.data.gained, reverse=True)
    for category in milestone_categories.values():
        category.sort(key=lambda item: item.created_at)
    achievements.sort(key=lambda item: item.created_at)
    name_changes.sort(key=lambda item: item.created_at)

    return _chunk_messages(
        _build_report_lines(
            start_date=start_date,
            end_date=end_date,
            overall_gains=overall_gains,
            ehb_gains=ehb_gains,
            ehp_gains=ehp_gains,
            sailing_gains=sailing_gains,
            name_changes=name_changes,
            achievements=achievements,
            player_name_map=player_name_map,
            boss_kc_achievements=milestone_categories["boss_kc"],
            xp_achievements=milestone_categories["xp"],
            level_achievements=milestone_categories["level"],
        )
    )


async def _send_report(discord_client, channel_id: int, messages: list[str], log) -> None:
    channel = discord_client.get_channel(channel_id)
    if channel is None:
        log(f"Monthly report: channel {channel_id} not found.")
        return
    for message in messages:
        await channel.send(message)


async def _monthly_report_loop(*, wom_client, discord_client, group_id: int, channel_id: int, log, debug: bool) -> None:
    while True:
        now = datetime.now(timezone.utc)
        next_run = _next_month_end(now)
        if debug:
            log(f"Monthly report scheduled for {next_run.isoformat()}")
        await asyncio.sleep(max((next_run - now).total_seconds(), 1))
        messages = await _generate_monthly_report(
            wom_client=wom_client, group_id=group_id, end_date=next_run, log=log
        )
        await _send_report(discord_client, channel_id, messages, log)


def start_monthly_reporter(*, wom_client, discord_client, group_id: int, channel_id: int, log, debug: bool = False) -> asyncio.Task:
    return asyncio.create_task(
        _monthly_report_loop(
            wom_client=wom_client,
            discord_client=discord_client,
            group_id=group_id,
            channel_id=channel_id,
            log=log,
            debug=debug,
        )
    )


def most_recent_month_end(now: datetime) -> datetime:
    """Return the most recent first-of-month 18:00 UTC boundary."""
    return _most_recent_month_end(now)


async def generate_monthly_report_messages(*, wom_client, group_id: int, end_date: datetime, log) -> list[str]:
    return await _generate_monthly_report(
        wom_client=wom_client, group_id=group_id, end_date=end_date, log=log
    )


async def send_monthly_report(*, discord_client, channel_id: int, messages: list[str], log) -> None:
    await _send_report(discord_client, channel_id, messages, log)
