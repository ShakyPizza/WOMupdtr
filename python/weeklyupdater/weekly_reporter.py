"""Weekly group report scheduler and data collector."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
import typing as t

from wom import enums
from wom.models.players.enums import AchievementMeasure


def _most_recent_sunday_1800_utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    days_since_sunday = (now.weekday() - 6) % 7
    target_date = (now - timedelta(days=days_since_sunday)).date()
    end = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        18,
        0,
        tzinfo=timezone.utc,
    )

    if now < end:
        end -= timedelta(days=7)

    return end


def _next_sunday_1800_utc(now: datetime) -> datetime:
    end = _most_recent_sunday_1800_utc(now)
    return end + timedelta(days=7)


def _format_int(value: t.Union[int, float]) -> str:
    return f"{int(round(value)):,}"


def _format_float(value: float) -> str:
    return f"{value:,.2f}"


async def _get_group_member_map(wom_client, group_id: int, log) -> dict[int, str]:
    result = await wom_client.groups.get_details(group_id)
    if not result.is_ok:
        log(f"Weekly report: failed to fetch group details: {result.unwrap_err()}")
        return {}

    group = result.unwrap()
    return {membership.player.id: membership.player.display_name for membership in group.memberships}


async def _get_group_gains(
    wom_client,
    group_id: int,
    metric: enums.Metric,
    start_date: datetime,
    end_date: datetime,
    *,
    limit: int = 50,
) -> list:
    result = await wom_client.groups.get_gains(
        group_id,
        metric,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=0,
    )

    if not result.is_ok:
        return []

    return list(result.unwrap())


async def _get_group_achievements(
    wom_client,
    group_id: int,
    start_date: datetime,
    end_date: datetime,
    log,
    *,
    limit: int = 50,
) -> list:
    achievements = []
    offset = 0

    while True:
        result = await wom_client.groups.get_achievements(group_id, limit=limit, offset=offset)
        if not result.is_ok:
            log(f"Weekly report: failed to fetch achievements: {result.unwrap_err()}")
            break

        page = list(result.unwrap())
        if not page:
            break

        for achievement in page:
            if start_date <= achievement.created_at < end_date:
                achievements.append(achievement)

        if page[-1].created_at < start_date:
            break

        offset += limit

    return achievements


async def _get_group_name_changes(
    wom_client,
    group_id: int,
    start_date: datetime,
    end_date: datetime,
    log,
    *,
    limit: int = 50,
) -> list:
    changes = []
    offset = 0

    while True:
        result = await wom_client.groups.get_name_changes(group_id, limit=limit, offset=offset)
        if not result.is_ok:
            log(f"Weekly report: failed to fetch name changes: {result.unwrap_err()}")
            break

        page = list(result.unwrap())
        if not page:
            break

        for change in page:
            if start_date <= change.created_at < end_date:
                changes.append(change)

        if page[-1].created_at < start_date:
            break

        offset += limit

    return changes


def _chunk_messages(lines: list[str], limit: int = 2000) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []

    for line in lines:
        tentative = "\n".join(current + [line])
        if len(tentative) > limit:
            if current:
                chunks.append("\n".join(current))
                current = [line]
            else:
                chunks.append(line[:limit])
                current = []
        else:
            current.append(line)

    if current:
        chunks.append("\n".join(current))

    return chunks


def _build_report_lines(
    *,
    start_date: datetime,
    end_date: datetime,
    overall_top: t.Optional[tuple[str, float]],
    ehb_top: list[tuple[str, float]],
    sailing_top: t.Optional[tuple[str, float]],
    name_changes: list,
    achievements: list,
    player_name_map: dict[int, str],
) -> list[str]:
    header = (
        "Weekly Report"
        f" ({start_date.strftime('%Y-%m-%d %H:%M')} UTC"
        f" - {end_date.strftime('%Y-%m-%d %H:%M')} UTC)"
    )

    lines = [header, ""]

    if overall_top:
        lines.append(
            f"Highest total XP gained: {overall_top[0]} (+{_format_int(overall_top[1])} xp)"
        )
    else:
        lines.append("Highest total XP gained: no data")

    if ehb_top:
        lines.append("Top EHB gainers:")
        for idx, (name, gained) in enumerate(ehb_top, start=1):
            lines.append(f"{idx}. {name} (+{_format_float(gained)} EHB)")
    else:
        lines.append("Top EHB gainers: no data")

    if sailing_top:
        lines.append(
            f"Pirate of the week: {sailing_top[0]} (+{_format_int(sailing_top[1])} Sailing xp)"
        )
    else:
        lines.append("Pirate of the week: no data")

    lines.append("")

    if name_changes:
        lines.append("Name changes:")
        for change in name_changes:
            timestamp = change.created_at.strftime("%Y-%m-%d")
            lines.append(
                f"- {change.old_name} -> {change.new_name} ({change.status.value}, {timestamp})"
            )
    else:
        lines.append("Name changes: none")

    if achievements:
        lines.append("New 99s:")
        for achievement in achievements:
            player_name = player_name_map.get(achievement.player_id, f"Player {achievement.player_id}")
            timestamp = achievement.created_at.strftime("%Y-%m-%d")
            lines.append(f"- {player_name}: {achievement.metric.value} ({timestamp})")
    else:
        lines.append("New 99s: none")

    return lines


async def _generate_weekly_report(
    *,
    wom_client,
    group_id: int,
    end_date: datetime,
    log,
) -> list[str]:
    start_date = end_date - timedelta(days=7)

    player_name_map = await _get_group_member_map(wom_client, group_id, log)

    overall_gains = await _get_group_gains(
        wom_client, group_id, enums.Metric.Overall, start_date, end_date, limit=50
    )
    ehb_gains = await _get_group_gains(
        wom_client, group_id, enums.Metric.Ehb, start_date, end_date, limit=50
    )
    sailing_gains = await _get_group_gains(
        wom_client, group_id, enums.Metric.Sailing, start_date, end_date, limit=50
    )

    name_changes = await _get_group_name_changes(
        wom_client, group_id, start_date, end_date, log, limit=50
    )
    achievements = await _get_group_achievements(
        wom_client, group_id, start_date, end_date, log, limit=50
    )

    overall_gains.sort(key=lambda entry: entry.data.gained, reverse=True)
    ehb_gains.sort(key=lambda entry: entry.data.gained, reverse=True)
    sailing_gains.sort(key=lambda entry: entry.data.gained, reverse=True)

    overall_top = None
    if overall_gains:
        overall_top = (
            overall_gains[0].player.display_name,
            overall_gains[0].data.gained,
        )

    ehb_top = [
        (entry.player.display_name, entry.data.gained) for entry in ehb_gains[:3]
    ]

    sailing_top = None
    if sailing_gains:
        sailing_top = (
            sailing_gains[0].player.display_name,
            sailing_gains[0].data.gained,
        )

    achievements = [
        achievement
        for achievement in achievements
        if achievement.measure == AchievementMeasure.Levels
        and achievement.threshold == 99
        and achievement.metric in enums.Skills
    ]
    achievements.sort(key=lambda item: item.created_at)

    name_changes.sort(key=lambda item: item.created_at)

    lines = _build_report_lines(
        start_date=start_date,
        end_date=end_date,
        overall_top=overall_top,
        ehb_top=ehb_top,
        sailing_top=sailing_top,
        name_changes=name_changes,
        achievements=achievements,
        player_name_map=player_name_map,
    )

    return _chunk_messages(lines)


async def _send_report(discord_client, channel_id: int, messages: list[str], log) -> None:
    channel = discord_client.get_channel(channel_id)
    if channel is None:
        log(f"Weekly report: channel {channel_id} not found.")
        return

    for message in messages:
        await channel.send(message)  # pyright: ignore[reportAttributeAccessIssue]


async def _weekly_report_loop(
    *,
    wom_client,
    discord_client,
    group_id: int,
    channel_id: int,
    log,
    debug: bool,
) -> None:
    while True:
        now = datetime.now(timezone.utc)
        next_run = _next_sunday_1800_utc(now)
        sleep_seconds = max((next_run - now).total_seconds(), 1)
        if debug:
            log(f"Weekly report scheduled for {next_run.isoformat()}")
        await asyncio.sleep(sleep_seconds)

        report_messages = await _generate_weekly_report(
            wom_client=wom_client,
            group_id=group_id,
            end_date=next_run,
            log=log,
        )
        await _send_report(discord_client, channel_id, report_messages, log)


def start_weekly_reporter(
    *,
    wom_client,
    discord_client,
    group_id: int,
    channel_id: int,
    log,
    debug: bool = False,
) -> asyncio.Task:
    return asyncio.create_task(
        _weekly_report_loop(
            wom_client=wom_client,
            discord_client=discord_client,
            group_id=group_id,
            channel_id=channel_id,
            log=log,
            debug=debug,
        )
    )


def most_recent_week_end(now: datetime) -> datetime:
    """Return the most recent Sunday 18:00 UTC before or at now."""
    return _most_recent_sunday_1800_utc(now)


async def generate_weekly_report_messages(
    *, wom_client, group_id: int, end_date: datetime, log
) -> list[str]:
    """Generate weekly report message chunks for the provided week window."""
    return await _generate_weekly_report(
        wom_client=wom_client,
        group_id=group_id,
        end_date=end_date,
        log=log,
    )


async def send_weekly_report(
    *, discord_client, channel_id: int, messages: list[str], log
) -> None:
    """Send weekly report messages to the configured Discord channel."""
    await _send_report(discord_client, channel_id, messages, log)
