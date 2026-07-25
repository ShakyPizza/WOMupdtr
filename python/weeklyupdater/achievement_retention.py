"""Normalize, persist, and present achievement events already fetched for reports."""

from __future__ import annotations

from datetime import datetime, timezone
import typing as t

from utils.database import upsert_achievement_events

_LEVEL_99_XP = 13_034_431


def _value(value: t.Any) -> t.Any:
    return getattr(value, "value", value)


def _text(value: t.Any) -> str | None:
    value = _value(value)
    if value is None:
        return None
    return str(value)


def _timestamp(value: t.Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _player_value(player: t.Any, name: str) -> t.Any:
    return getattr(player, name, None) if player is not None else None


def _achievement_row(
    achievement: t.Any,
    group_id: int,
    player_name_map: dict[int, str],
) -> dict | None:
    player_id = getattr(achievement, "player_id", None)
    metric = _text(getattr(achievement, "metric", None))
    measure = _text(getattr(achievement, "measure", None))
    threshold = getattr(achievement, "threshold", None)
    if player_id is None or not metric or not measure or threshold is None:
        return None

    player = getattr(achievement, "player", None)
    fallback_name = player_name_map.get(player_id)
    return {
        "player_id": player_id,
        "source_group_id": group_id,
        "current_username": _player_value(player, "username") or fallback_name,
        "display_name": _player_value(player, "display_name") or fallback_name,
        "account_type": _text(_player_value(player, "type")),
        "build": _text(_player_value(player, "build")),
        "status": _text(_player_value(player, "status")),
        "overall_xp": _player_value(player, "exp"),
        "ehp": _player_value(player, "ehp"),
        "ehb": _player_value(player, "ehb"),
        "ttm": _player_value(player, "ttm"),
        "tt200m": _player_value(player, "tt200m"),
        "registered_at": _timestamp(_player_value(player, "registered_at")),
        "wom_updated_at": _timestamp(_player_value(player, "updated_at")),
        "last_changed_at": _timestamp(_player_value(player, "last_changed_at")),
        "last_imported_at": _timestamp(_player_value(player, "last_imported_at")),
        "metric": metric,
        "measure": measure,
        "threshold": threshold,
        "name": getattr(achievement, "name", None),
        "achieved_at": _timestamp(getattr(achievement, "created_at", None)),
        "accuracy_ms": getattr(achievement, "accuracy", None),
        "legacy": (
            bool(achievement.legacy)
            if hasattr(achievement, "legacy")
            else None
        ),
    }


def persist_fetched_achievements(
    achievements: list,
    *,
    group_id: int,
    player_name_map: dict[int, str],
    log,
) -> int:
    """Persist fetched achievements without making report generation depend on storage."""
    rows = [
        row
        for achievement in achievements
        if (
            row := _achievement_row(achievement, group_id, player_name_map)
        ) is not None
    ]
    try:
        return upsert_achievement_events(rows)
    except Exception as exc:
        log(f"Achievement retention failed: {exc}")
        return 0


def categorize_additional_milestones(achievements: list) -> dict[str, list]:
    """Return non-99 boss-KC, XP, and level milestone categories."""
    categories = {"boss_kc": [], "xp": [], "level": []}
    for achievement in achievements:
        measure = (_text(getattr(achievement, "measure", None)) or "").lower()
        try:
            threshold = int(getattr(achievement, "threshold"))
        except (TypeError, ValueError):
            continue
        if measure in {"kill", "kills"}:
            categories["boss_kc"].append(achievement)
        elif measure in {"experience", "xp", "exp"} and threshold != _LEVEL_99_XP:
            categories["xp"].append(achievement)
        elif measure in {"level", "levels"} and threshold != 99:
            categories["level"].append(achievement)
    return categories


def format_milestone_line(achievement: t.Any, player_name_map: dict[int, str]) -> str:
    """Format one achievement for a report milestone section."""
    player_id = getattr(achievement, "player_id", None)
    embedded_player = getattr(achievement, "player", None)
    player_name = player_name_map.get(
        player_id,
        getattr(embedded_player, "display_name", f"Player {player_id}"),
    )
    name = getattr(achievement, "name", None)
    if not name:
        metric = (_text(getattr(achievement, "metric", None)) or "unknown").replace("_", " ")
        threshold = getattr(achievement, "threshold", "?")
        measure = _text(getattr(achievement, "measure", None)) or "milestone"
        try:
            threshold = f"{int(threshold):,}"
        except (TypeError, ValueError):
            threshold = str(threshold)
        name = f"{threshold} {metric} {measure}"
    created_at = getattr(achievement, "created_at", None)
    date_label = created_at.strftime("%Y-%m-%d") if isinstance(created_at, datetime) else "date unknown"
    return f"- {player_name}: {name} ({date_label})"


def append_milestone_sections(
    lines: list[str],
    *,
    boss_kc: list,
    xp: list,
    level: list,
    player_name_map: dict[int, str],
) -> None:
    """Append only populated milestone sections, preserving empty-report output."""
    sections = (
        ("Boss KC milestones", boss_kc),
        ("XP milestones", xp),
        ("Level milestones", level),
    )
    for title, achievements in sections:
        if not achievements:
            continue
        lines.extend(["", f"{title}:"])
        lines.extend(format_milestone_line(item, player_name_map) for item in achievements)
