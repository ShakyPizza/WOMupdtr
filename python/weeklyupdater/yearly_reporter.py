"""Yearly group report scheduler and data collector."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import typing as t

from wom import enums
from wom.models.players.enums import AchievementMeasure


RATE_LIMIT_DELAY_SECONDS = 1.5
_SKILL_METRIC_VALUES = {getattr(metric, "value", metric) for metric in enums.Skills}
_LEVEL_99_XP = 13_034_431


def _year_boundary_1200_utc(year: int) -> datetime:
    return datetime(year, 1, 1, 12, 0, tzinfo=timezone.utc)


def _most_recent_jan1_1200_utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    boundary = _year_boundary_1200_utc(now.year)
    if now < boundary:
        boundary = _year_boundary_1200_utc(now.year - 1)
    return boundary


def _next_jan1_1200_utc(now: datetime) -> datetime:
    boundary = _most_recent_jan1_1200_utc(now)
    return _year_boundary_1200_utc(boundary.year + 1)


def _format_int(value: t.Union[int, float]) -> str:
    return f"{int(round(value)):,}"


def _format_float(value: float) -> str:
    return f"{value:,.2f}"


def _is_level_measure(measure: t.Any) -> bool:
    if measure == AchievementMeasure.Levels:
        return True
    level_measure = getattr(AchievementMeasure, "Level", None)
    if level_measure is not None and measure == level_measure:
        return True
    value = getattr(measure, "value", None)
    if value is None and isinstance(measure, str):
        value = measure
    if value is None:
        return False
    return str(value).lower() in {"level", "levels"}


def _is_experience_measure(measure: t.Any) -> bool:
    experience_measure = getattr(AchievementMeasure, "Experience", None)
    if experience_measure is not None and measure == experience_measure:
        return True
    value = getattr(measure, "value", None)
    if value is None and isinstance(measure, str):
        value = measure
    if value is None:
        return False
    return str(value).lower() in {"experience", "xp", "exp"}


def _is_skill_metric(metric: t.Any) -> bool:
    if metric in enums.Skills:
        return True
    value = getattr(metric, "value", None)
    if value is None and isinstance(metric, str):
        value = metric
    if value is None:
        return False
    return value in _SKILL_METRIC_VALUES


def _metric_label(metric: t.Any) -> str:
    value = getattr(metric, "value", None)
    if value is None:
        return str(metric)
    return str(value)


def _matches_threshold(value: t.Any, target: int) -> bool:
    try:
        return int(float(value)) == target
    except (TypeError, ValueError):
        return False


async def _get_group_member_map(wom_client, group_id: int, log) -> dict[int, str]:
    result = await wom_client.groups.get_details(group_id)
    if not result.is_ok:
        log(f"Yearly report: failed to fetch group details: {result.unwrap_err()}")
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
            log(f"Yearly report: failed to fetch achievements: {result.unwrap_err()}")
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
        await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)

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
            log(f"Yearly report: failed to fetch name changes: {result.unwrap_err()}")
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
        await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)

    return changes


async def _get_group_statistics(wom_client, group_id: int, log):
    result = await wom_client.groups.get_statistics(group_id)
    if not result.is_ok:
        log(f"Yearly report: failed to fetch group statistics: {result.unwrap_err()}")
        return None
    return result.unwrap()


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


def _add_limited_list(lines: list[str], entries: list[str], *, limit: int, suffix: str) -> None:
    if len(entries) <= limit:
        lines.extend(entries)
        return

    lines.extend(entries[:limit])
    remaining = len(entries) - limit
    lines.append(f"...and {remaining} more {suffix}")


def _build_report_lines(
    *,
    start_date: datetime,
    end_date: datetime,
    overall_gains: list,
    ehb_gains: list,
    ehp_gains: list,
    sailing_gains: list,
    name_changes: list,
    achievements_99s: list,
    achievements_max_total: list,
    player_name_map: dict[int, str],
    group_stats,
) -> list[str]:
    year_label = start_date.strftime("%Y")
    header = (
        f"Yearly Report {year_label}"
        f" ({start_date.strftime('%d-%m-%Y %H:%M')} UTC"
        f" - {end_date.strftime('%d-%m-%Y %H:%M')} UTC)"
    )

    lines = [header, ""]

    total_members = len(player_name_map)
    active_members = len(overall_gains)

    total_xp = sum(entry.data.gained for entry in overall_gains)
    avg_xp = total_xp / active_members if active_members else 0

    lines.append("Overall XP")
    lines.append(f"- Group total gained: {_format_int(total_xp)} xp")
    lines.append(f"- Active gainers: {active_members}/{total_members} members")
    lines.append(f"- Average per active member: {_format_int(avg_xp)} xp")
    if overall_gains:
        lines.append("Top overall XP gainers:")
        for idx, entry in enumerate(overall_gains[:10], start=1):
            lines.append(f"{idx}. {entry.player.display_name} (+{_format_int(entry.data.gained)} xp)")
    else:
        lines.append("Top overall XP gainers: no data")
    lines.append("")

    total_ehb = sum(entry.data.gained for entry in ehb_gains)
    total_ehp = sum(entry.data.gained for entry in ehp_gains)

    lines.append("Efficiency Hours")
    lines.append(f"- Group total EHB gained: {_format_float(total_ehb)}")
    lines.append(f"- Group total EHP gained: {_format_float(total_ehp)}")
    if ehb_gains:
        lines.append("Top EHB gainers:")
        for idx, entry in enumerate(ehb_gains[:10], start=1):
            lines.append(f"{idx}. {entry.player.display_name} (+{_format_float(entry.data.gained)} EHB)")
    else:
        lines.append("Top EHB gainers: no data")
    if ehp_gains:
        lines.append("Top EHP gainers:")
        for idx, entry in enumerate(ehp_gains[:10], start=1):
            lines.append(f"{idx}. {entry.player.display_name} (+{_format_float(entry.data.gained)} EHP)")
    else:
        lines.append("Top EHP gainers: no data")
    lines.append("")

    total_sailing = sum(entry.data.gained for entry in sailing_gains)
    lines.append("Sailing Spotlight")
    lines.append(f"- Group total Sailing XP: {_format_int(total_sailing)} xp")
    if sailing_gains:
        lines.append("Top Sailing gainers:")
        for idx, entry in enumerate(sailing_gains[:5], start=1):
            lines.append(f"{idx}. {entry.player.display_name} (+{_format_int(entry.data.gained)} xp)")
    else:
        lines.append("Top Sailing gainers: no data")
    lines.append("")

    lines.append("Milestones")
    if achievements_max_total:
        lines.append("Special congratulations to these maxed total level (2376) players:")
        total_lines = []
        for achievement in achievements_max_total:
            player_name = player_name_map.get(achievement.player_id, f"Player {achievement.player_id}")
            timestamp = achievement.created_at.strftime("%d-%m-%Y")
            total_lines.append(f"- {player_name} ({timestamp})")
        _add_limited_list(lines, total_lines, limit=10, suffix="maxed players")
    else:
        lines.append("Total level 2376 achieved: none this year")

    if achievements_99s:
        lines.append(f"New 99s: {len(achievements_99s)}")
        grouped_99s: dict[str, list[tuple[str, str]]] = {}
        for achievement in achievements_99s:
            player_name = player_name_map.get(achievement.player_id, f"Player {achievement.player_id}")
            timestamp = achievement.created_at.strftime("%d-%m-%Y")
            grouped_99s.setdefault(player_name, []).append(
                (_metric_label(achievement.metric), timestamp)
            )
        for player_name in sorted(grouped_99s.keys(), key=str.casefold):
            entries = grouped_99s[player_name]
            entries.sort(key=lambda item: item[1])
            details = ", ".join(f"{metric} ({timestamp})" for metric, timestamp in entries)
            lines.append(f"- {player_name}: {details}")
    else:
        lines.append("New 99s: none")
    lines.append("")

    if name_changes:
        lines.append(f"Name changes: {len(name_changes)}")
        change_lines = []
        for change in name_changes:
            timestamp = change.created_at.strftime("%d-%m-%Y")
            change_lines.append(
                f"- {change.old_name} -> {change.new_name} ({change.status.value}, {timestamp})"
            )
        _add_limited_list(lines, change_lines, limit=10, suffix="name changes")
    else:
        lines.append("Name changes: none")
    lines.append("")

    if group_stats:
        avg_snapshot = group_stats.average_stats
        average_total_level = None
        average_total_xp = None
        if avg_snapshot and avg_snapshot.data and avg_snapshot.data.skills:
            overall_skill = avg_snapshot.data.skills.get(enums.Metric.Overall)
            if overall_skill:
                average_total_level = overall_skill.level
                average_total_xp = overall_skill.experience

        lines.append("Group Snapshot")
        lines.append(f"- Maxed total count: {group_stats.maxed_total_count}")
        lines.append(f"- Maxed combat count: {group_stats.maxed_combat_count}")
        lines.append(f"- Maxed 200m count: {group_stats.maxed_200ms_count}")
        if average_total_level is not None:
            lines.append(f"- Average total level: {average_total_level}")
        if average_total_xp is not None:
            lines.append(f"- Average total XP: {_format_int(average_total_xp)} xp")
        lines.append("")

    return lines


async def _generate_yearly_report(
    *,
    wom_client,
    group_id: int,
    end_date: datetime,
    log,
) -> list[str]:
    start_date = _year_boundary_1200_utc(end_date.year - 1)

    player_name_map = await _get_group_member_map(wom_client, group_id, log)

    overall_gains = await _get_group_gains(
        wom_client, group_id, enums.Metric.Overall, start_date, end_date, limit=50
    )
    await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
    ehb_gains = await _get_group_gains(
        wom_client, group_id, enums.Metric.Ehb, start_date, end_date, limit=50
    )
    await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
    ehp_gains = await _get_group_gains(
        wom_client, group_id, enums.Metric.Ehp, start_date, end_date, limit=50
    )
    await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
    sailing_gains = await _get_group_gains(
        wom_client, group_id, enums.Metric.Sailing, start_date, end_date, limit=50
    )
    await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)

    name_changes = await _get_group_name_changes(
        wom_client, group_id, start_date, end_date, log, limit=50
    )
    await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
    achievements = await _get_group_achievements(
        wom_client, group_id, start_date, end_date, log, limit=50
    )
    await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
    group_stats = await _get_group_statistics(wom_client, group_id, log)

    overall_gains.sort(key=lambda entry: entry.data.gained, reverse=True)
    ehb_gains.sort(key=lambda entry: entry.data.gained, reverse=True)
    ehp_gains.sort(key=lambda entry: entry.data.gained, reverse=True)
    sailing_gains.sort(key=lambda entry: entry.data.gained, reverse=True)

    achievements_99s = [
        achievement
        for achievement in achievements
        if _is_skill_metric(achievement.metric)
        and (
            (_is_level_measure(achievement.measure) and _matches_threshold(achievement.threshold, 99))
            or (
                _is_experience_measure(achievement.measure)
                and _matches_threshold(achievement.threshold, _LEVEL_99_XP)
            )
        )
    ]
    achievements_99s.sort(key=lambda item: item.created_at)

    achievements_max_total = [
        achievement
        for achievement in achievements
        if _is_level_measure(achievement.measure)
        and achievement.metric == enums.Metric.Overall
        and _matches_threshold(achievement.threshold, 2376)
    ]
    achievements_max_total.sort(key=lambda item: item.created_at)

    name_changes.sort(key=lambda item: item.created_at)

    if achievements and not achievements_99s:
        sample_lines = []
        for achievement in achievements[:5]:
            sample_lines.append(
                f"{_metric_label(achievement.metric)}:"
                f"{getattr(achievement.measure, 'value', achievement.measure)}"
                f"/{achievement.threshold}"
            )
        log("Yearly report: no 99s matched; sample achievements " + ", ".join(sample_lines))

    lines = _build_report_lines(
        start_date=start_date,
        end_date=end_date,
        overall_gains=overall_gains,
        ehb_gains=ehb_gains,
        ehp_gains=ehp_gains,
        sailing_gains=sailing_gains,
        name_changes=name_changes,
        achievements_99s=achievements_99s,
        achievements_max_total=achievements_max_total,
        player_name_map=player_name_map,
        group_stats=group_stats,
    )

    return _chunk_messages(lines)


async def _send_report(discord_client, channel_id: int, messages: list[str], log) -> None:
    channel = discord_client.get_channel(channel_id)
    if channel is None:
        log(f"Yearly report: channel {channel_id} not found.")
        return

    for message in messages:
        await channel.send(message)  # pyright: ignore[reportAttributeAccessIssue]


async def _yearly_report_loop(
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
        next_run = _next_jan1_1200_utc(now)
        sleep_seconds = max((next_run - now).total_seconds(), 1)
        if debug:
            log(f"Yearly report scheduled for {next_run.isoformat()}")
        await asyncio.sleep(sleep_seconds)

        report_messages = await _generate_yearly_report(
            wom_client=wom_client,
            group_id=group_id,
            end_date=next_run,
            log=log,
        )
        await _send_report(discord_client, channel_id, report_messages, log)


def start_yearly_reporter(
    *,
    wom_client,
    discord_client,
    group_id: int,
    channel_id: int,
    log,
    debug: bool = False,
) -> asyncio.Task:
    return asyncio.create_task(
        _yearly_report_loop(
            wom_client=wom_client,
            discord_client=discord_client,
            group_id=group_id,
            channel_id=channel_id,
            log=log,
            debug=debug,
        )
    )


def most_recent_year_end(now: datetime) -> datetime:
    """Return the most recent Jan 1 12:00 UTC before or at now."""
    return _most_recent_jan1_1200_utc(now)


async def generate_yearly_report_messages(
    *, wom_client, group_id: int, end_date: datetime, log
) -> list[str]:
    """Generate yearly report message chunks for the provided year window."""
    return await _generate_yearly_report(
        wom_client=wom_client,
        group_id=group_id,
        end_date=end_date,
        log=log,
    )


async def send_yearly_report(
    *, discord_client, channel_id: int, messages: list[str], log
) -> None:
    """Send yearly report messages to the configured Discord channel."""
    await _send_report(discord_client, channel_id, messages, log)


async def write_yearly_report_file(
    *, output_path: str, messages: list[str], log
) -> None:
    """Write yearly report messages to a local file for debugging."""
    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            content = "\n\n".join(messages).rstrip()
            if content:
                handle.write(content + "\n")
            else:
                handle.write("")
        log(f"Yearly report written to {output_path}")
    except Exception as exc:
        log(f"Yearly report: failed to write {output_path}: {exc}")
        raise
