"""Tests for pure / deterministic helper functions in the weekly and yearly reporters."""

import asyncio
import os
import sqlite3
import types
from datetime import datetime, timezone

import pytest
from wom import enums

from python.weeklyupdater import weekly_reporter
from python.weeklyupdater import monthly_reporter
from python.weeklyupdater import yearly_reporter
from python.weeklyupdater import achievement_retention


# ---------------------------------------------------------------------------
# weekly_reporter — most_recent_week_end / _most_recent_sunday_1800_utc
# ---------------------------------------------------------------------------

def test_most_recent_week_end_returns_previous_sunday_on_monday():
    """Called on a Monday it returns the most recent Sunday at 18:00 UTC."""
    # 2025-06-09 is a Monday at 20:00 UTC
    now = datetime(2025, 6, 9, 20, 0, tzinfo=timezone.utc)
    result = weekly_reporter.most_recent_week_end(now)
    assert result.weekday() == 6           # 6 = Sunday
    assert result.hour == 18
    assert result.minute == 0
    assert result.tzinfo == timezone.utc
    # 2025-06-08 is the previous Sunday
    assert result.date().isoformat() == "2025-06-08"


def test_most_recent_week_end_returns_current_sunday_after_1800():
    """Called on a Sunday after 18:00 UTC it returns today."""
    # 2025-06-08 is a Sunday at 19:00 UTC
    now = datetime(2025, 6, 8, 19, 0, tzinfo=timezone.utc)
    result = weekly_reporter.most_recent_week_end(now)
    assert result.date().isoformat() == "2025-06-08"
    assert result.hour == 18


def test_most_recent_week_end_returns_previous_sunday_before_1800():
    """Called on a Sunday before 18:00 UTC it returns the prior Sunday."""
    # 2025-06-08 is a Sunday at 10:00 UTC (before 18:00)
    now = datetime(2025, 6, 8, 10, 0, tzinfo=timezone.utc)
    result = weekly_reporter.most_recent_week_end(now)
    assert result.date().isoformat() == "2025-06-01"  # previous Sunday


def test_most_recent_week_end_raises_for_naive_datetime():
    """Naive datetimes (no tzinfo) are rejected with ValueError."""
    now = datetime(2025, 6, 9, 20, 0)  # no tzinfo
    with pytest.raises(ValueError):
        weekly_reporter.most_recent_week_end(now)


# ---------------------------------------------------------------------------
# yearly_reporter — most_recent_year_end / _most_recent_jan1_1800_utc
# ---------------------------------------------------------------------------

def test_most_recent_year_end_returns_current_year_jan1_after_1800():
    """Called on Jan 1 after 18:00 UTC it returns the current year's boundary."""
    now = datetime(2026, 1, 1, 19, 0, tzinfo=timezone.utc)
    result = yearly_reporter.most_recent_year_end(now)
    assert result == datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)


def test_most_recent_year_end_returns_previous_year_before_1800_on_jan1():
    """Called on Jan 1 before 18:00 UTC it returns the previous year's boundary."""
    now = datetime(2026, 1, 1, 17, 0, tzinfo=timezone.utc)
    result = yearly_reporter.most_recent_year_end(now)
    assert result == datetime(2025, 1, 1, 18, 0, tzinfo=timezone.utc)


def test_most_recent_year_end_mid_year_returns_current_year_jan1():
    """Called mid-year (e.g. June) it returns Jan 1 of the current year."""
    now = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    result = yearly_reporter.most_recent_year_end(now)
    assert result == datetime(2025, 1, 1, 18, 0, tzinfo=timezone.utc)


def test_most_recent_year_end_raises_for_naive_datetime():
    """Naive datetimes are rejected."""
    now = datetime(2025, 6, 15, 12, 0)  # no tzinfo
    with pytest.raises(ValueError):
        yearly_reporter.most_recent_year_end(now)


# ---------------------------------------------------------------------------
# monthly_reporter — completed calendar-month boundaries and output
# ---------------------------------------------------------------------------


def test_most_recent_month_end_uses_current_month_boundary_after_1800():
    now = datetime(2025, 6, 15, 8, 0, tzinfo=timezone.utc)
    assert monthly_reporter.most_recent_month_end(now) == datetime(
        2025, 6, 1, 18, 0, tzinfo=timezone.utc
    )


def test_most_recent_month_end_rolls_back_before_boundary():
    now = datetime(2025, 6, 1, 17, 59, tzinfo=timezone.utc)
    assert monthly_reporter.most_recent_month_end(now) == datetime(
        2025, 5, 1, 18, 0, tzinfo=timezone.utc
    )


def test_monthly_report_includes_totals_and_ehp_leaders():
    def gain(name, value):
        player = types.SimpleNamespace(display_name=name)
        return types.SimpleNamespace(player=player, data=types.SimpleNamespace(gained=value))

    lines = monthly_reporter._build_report_lines(
        start_date=datetime(2025, 5, 1, 12, 0, tzinfo=timezone.utc),
        end_date=datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
        overall_gains=[gain("Alice", 2_000_000)],
        ehb_gains=[gain("Bob", 12.5)],
        ehp_gains=[gain("Carol", 8.25)],
        sailing_gains=[],
        name_changes=[],
        achievements=[],
        player_name_map={1: "Alice", 2: "Bob"},
    )
    report = "\n".join(lines)
    assert "Monthly Report - May 2025" in report
    assert "Group XP gained: 2,000,000 xp" in report
    assert "Carol (+8.25 EHP)" in report


# weekly_reporter._chunk_messages
# ---------------------------------------------------------------------------

def test_chunk_messages_single_chunk_when_all_fit():
    """Short lines that fit within the limit are returned as one chunk."""
    lines = ["line one", "line two", "line three"]
    chunks = weekly_reporter._chunk_messages(lines, limit=2000)
    assert len(chunks) == 1
    assert chunks[0] == "line one\nline two\nline three"


def test_chunk_messages_splits_when_limit_exceeded():
    """Lines are split into multiple chunks when combined length exceeds limit."""
    # Each line is 10 chars; limit forces a split after first line
    line = "a" * 10
    lines = [line] * 5
    chunks = weekly_reporter._chunk_messages(lines, limit=15)
    assert len(chunks) > 1
    # No chunk exceeds the limit
    for chunk in chunks:
        assert len(chunk) <= 15


def test_chunk_messages_empty_input_returns_empty_list():
    """Empty input produces no chunks."""
    assert weekly_reporter._chunk_messages([]) == []


def test_chunk_messages_single_oversized_line_is_truncated():
    """A single line longer than limit is truncated to fit."""
    line = "x" * 3000
    chunks = weekly_reporter._chunk_messages([line], limit=2000)
    assert len(chunks) == 1
    assert len(chunks[0]) == 2000


def test_chunk_messages_yearly_same_behaviour():
    """yearly_reporter._chunk_messages behaves identically."""
    lines = ["alpha", "beta", "gamma"]
    assert yearly_reporter._chunk_messages(lines) == weekly_reporter._chunk_messages(lines)


# ---------------------------------------------------------------------------
# weekly_reporter._build_report_lines
# ---------------------------------------------------------------------------

def _fake_name_change(old_name, new_name, status_value, dt):
    return types.SimpleNamespace(
        old_name=old_name,
        new_name=new_name,
        status=types.SimpleNamespace(value=status_value),
        created_at=dt,
    )


def _fake_achievement(
    player_id,
    metric_value,
    dt,
    *,
    measure_value=None,
    threshold=None,
    name=None,
):
    player = types.SimpleNamespace(
        username="hero player",
        display_name="Hero Player",
        type=types.SimpleNamespace(value="regular"),
        build=types.SimpleNamespace(value="main"),
        status=types.SimpleNamespace(value="active"),
        exp=123_456,
        ehp=12.5,
        ehb=3.5,
    )
    return types.SimpleNamespace(
        player_id=player_id,
        metric=enums.Metric(str(metric_value).lower()),
        measure=(
            types.SimpleNamespace(value=measure_value)
            if measure_value is not None
            else None
        ),
        threshold=threshold,
        name=name,
        created_at=dt,
        accuracy=500,
        legacy=False,
        player=player,
    )


def test_build_report_lines_contains_header():
    """Output contains a header with the date range."""
    start = datetime(2025, 6, 1, 18, 0, tzinfo=timezone.utc)
    end = datetime(2025, 6, 8, 18, 0, tzinfo=timezone.utc)
    lines = weekly_reporter._build_report_lines(
        start_date=start,
        end_date=end,
        overall_top=None,
        ehb_top=[],
        sailing_top=None,
        name_changes=[],
        achievements=[],
        player_name_map={},
    )
    assert any("Weekly Report" in line for line in lines)
    assert any("2025-06-01" in line for line in lines)
    assert any("2025-06-08" in line for line in lines)


def test_build_report_lines_no_data_placeholders():
    """When all data is absent, placeholder 'no data' / 'none' lines appear."""
    start = datetime(2025, 6, 1, 18, 0, tzinfo=timezone.utc)
    end = datetime(2025, 6, 8, 18, 0, tzinfo=timezone.utc)
    lines = weekly_reporter._build_report_lines(
        start_date=start,
        end_date=end,
        overall_top=None,
        ehb_top=[],
        sailing_top=None,
        name_changes=[],
        achievements=[],
        player_name_map={},
    )
    combined = "\n".join(lines)
    assert "no data" in combined.lower() or "none" in combined.lower()


def test_build_report_lines_includes_overall_top():
    """overall_top tuple is rendered in the output."""
    start = datetime(2025, 6, 1, 18, 0, tzinfo=timezone.utc)
    end = datetime(2025, 6, 8, 18, 0, tzinfo=timezone.utc)
    lines = weekly_reporter._build_report_lines(
        start_date=start,
        end_date=end,
        overall_top=("TopPlayer", 1_500_000),
        ehb_top=[],
        sailing_top=None,
        name_changes=[],
        achievements=[],
        player_name_map={},
    )
    combined = "\n".join(lines)
    assert "TopPlayer" in combined
    assert "1,500,000" in combined


def test_build_report_lines_includes_ehb_top_gainers():
    """Top EHB gainers are listed with their gained values."""
    start = datetime(2025, 6, 1, 18, 0, tzinfo=timezone.utc)
    end = datetime(2025, 6, 8, 18, 0, tzinfo=timezone.utc)
    lines = weekly_reporter._build_report_lines(
        start_date=start,
        end_date=end,
        overall_top=None,
        ehb_top=[("Alice", 12.5), ("Bob", 8.0)],
        sailing_top=None,
        name_changes=[],
        achievements=[],
        player_name_map={},
    )
    combined = "\n".join(lines)
    assert "Alice" in combined
    assert "12.50" in combined
    assert "Bob" in combined


def test_build_report_lines_includes_weekly_totals_and_ehp_gainers():
    start = datetime(2025, 6, 1, 18, 0, tzinfo=timezone.utc)
    end = datetime(2025, 6, 8, 18, 0, tzinfo=timezone.utc)
    lines = weekly_reporter._build_report_lines(
        start_date=start,
        end_date=end,
        overall_top=("Alice", 2_000_000),
        ehb_top=[],
        sailing_top=None,
        name_changes=[],
        achievements=[],
        player_name_map={1: "Alice", 2: "Bob"},
        total_xp=3_000_000,
        active_members=2,
        total_ehb=10.5,
        ehp_top=[("Bob", 7.25)],
        total_ehp=12.0,
    )
    report = "\n".join(lines)
    assert "Week at a glance" in report
    assert "Group XP gained: 3,000,000 xp" in report
    assert "Active gainers: 2/2 members" in report
    assert "Bob (+7.25 EHP)" in report


def test_build_report_lines_name_changes_rendered():
    """Name changes are listed correctly."""
    start = datetime(2025, 6, 1, 18, 0, tzinfo=timezone.utc)
    end = datetime(2025, 6, 8, 18, 0, tzinfo=timezone.utc)
    dt = datetime(2025, 6, 3, 12, 0, tzinfo=timezone.utc)
    changes = [_fake_name_change("OldName", "NewName", "approved", dt)]
    lines = weekly_reporter._build_report_lines(
        start_date=start,
        end_date=end,
        overall_top=None,
        ehb_top=[],
        sailing_top=None,
        name_changes=changes,
        achievements=[],
        player_name_map={},
    )
    combined = "\n".join(lines)
    assert "OldName" in combined
    assert "NewName" in combined


def test_build_report_lines_achievements_rendered():
    """Achievements appear in the 99s section."""
    start = datetime(2025, 6, 1, 18, 0, tzinfo=timezone.utc)
    end = datetime(2025, 6, 8, 18, 0, tzinfo=timezone.utc)
    dt = datetime(2025, 6, 4, 0, 0, tzinfo=timezone.utc)
    achievements = [_fake_achievement(42, "Attack", dt)]
    player_name_map = {42: "HeroPlayer"}
    lines = weekly_reporter._build_report_lines(
        start_date=start,
        end_date=end,
        overall_top=None,
        ehb_top=[],
        sailing_top=None,
        name_changes=[],
        achievements=achievements,
        player_name_map=player_name_map,
    )
    combined = "\n".join(lines)
    assert "HeroPlayer" in combined
    assert "attack" in combined.lower()


def test_additional_achievement_categories_exclude_99s():
    dt = datetime(2025, 6, 4, tzinfo=timezone.utc)
    achievements = [
        _fake_achievement(
            42,
            "zulrah",
            dt,
            measure_value="kills",
            threshold=500,
            name="500 Zulrah kills",
        ),
        _fake_achievement(
            42,
            "agility",
            dt,
            measure_value="experience",
            threshold=50_000_000,
            name="50m Agility",
        ),
        _fake_achievement(
            42,
            "overall",
            dt,
            measure_value="levels",
            threshold=2000,
            name="2000 Total Level",
        ),
        _fake_achievement(
            42,
            "attack",
            dt,
            measure_value="experience",
            threshold=13_034_431,
            name="99 Attack",
        ),
    ]

    categories = achievement_retention.categorize_additional_milestones(achievements)

    assert [item.name for item in categories["boss_kc"]] == ["500 Zulrah kills"]
    assert [item.name for item in categories["xp"]] == ["50m Agility"]
    assert [item.name for item in categories["level"]] == ["2000 Total Level"]


def test_weekly_report_renders_and_persists_boss_kc_from_existing_fetch(monkeypatch):
    dt = datetime(2025, 6, 4, tzinfo=timezone.utc)
    achievement = _fake_achievement(
        42,
        "zulrah",
        dt,
        measure_value="kills",
        threshold=500,
        name="500 Zulrah kills",
    )
    # wom.py's Achievement model may omit the embedded Player even though the
    # group endpoint supplies player_id; the already-fetched member map fills
    # the stable identity/alias in that case.
    achievement.player = None

    async def no_gains(*_args, **_kwargs):
        return []

    async def member_map(*_args, **_kwargs):
        return {42: "Hero Player"}

    async def no_changes(*_args, **_kwargs):
        return []

    async def achievements(*_args, **_kwargs):
        return [achievement]

    monkeypatch.setattr(weekly_reporter, "_get_group_gains", no_gains)
    monkeypatch.setattr(weekly_reporter, "_get_group_member_map", member_map)
    monkeypatch.setattr(weekly_reporter, "_get_group_name_changes", no_changes)
    monkeypatch.setattr(weekly_reporter, "_get_group_achievements", achievements)

    report = "\n".join(
        asyncio.run(
            weekly_reporter._generate_weekly_report(
                wom_client=object(),
                group_id=7,
                end_date=datetime(2025, 6, 8, 18, 0, tzinfo=timezone.utc),
                log=lambda _message: None,
            )
        )
    )

    assert "Boss KC milestones" in report
    assert "500 Zulrah kills" in report
    with sqlite3.connect(os.environ["WOM_DATABASE_PATH"]) as conn:
        row = conn.execute(
            "SELECT player_id, metric, measure, threshold FROM achievements"
        ).fetchone()
        player = conn.execute(
            "SELECT player_id, display_name FROM wom_players"
        ).fetchone()
        alias = conn.execute(
            "SELECT normalized_name FROM player_aliases"
        ).fetchone()
    assert row == (42, "zulrah", "kills", 500)
    assert player == (42, "Hero Player")
    assert alias == ("hero player",)


@pytest.mark.parametrize("reporter_name", ["monthly", "yearly"])
def test_longer_reports_persist_existing_achievement_fetches(monkeypatch, reporter_name):
    dt = datetime(2024, 6, 4, tzinfo=timezone.utc)
    achievement = _fake_achievement(
        42,
        "agility",
        dt,
        measure_value="experience",
        threshold=50_000_000,
        name="50m Agility",
    )

    async def no_gains(*_args, **_kwargs):
        return []

    async def member_map(*_args, **_kwargs):
        return {42: "Hero Player"}

    if reporter_name == "monthly":
        async def dated_pages(*_args, **kwargs):
            return [achievement] if kwargs["label"] == "achievements" else []

        monkeypatch.setattr(monthly_reporter, "_get_group_gains", no_gains)
        monkeypatch.setattr(monthly_reporter, "_get_group_member_map", member_map)
        monkeypatch.setattr(monthly_reporter, "_get_dated_pages", dated_pages)
        messages = asyncio.run(
            monthly_reporter._generate_monthly_report(
                wom_client=types.SimpleNamespace(groups=object()),
                group_id=7,
                end_date=datetime(2024, 7, 1, 18, 0, tzinfo=timezone.utc),
                log=lambda _message: None,
            )
        )
    else:
        async def no_changes(*_args, **_kwargs):
            return []

        async def achievements(*_args, **_kwargs):
            return [achievement]

        async def no_stats(*_args, **_kwargs):
            return None

        async def no_sleep(*_args, **_kwargs):
            return None

        monkeypatch.setattr(yearly_reporter, "_get_group_gains", no_gains)
        monkeypatch.setattr(yearly_reporter, "_get_group_member_map", member_map)
        monkeypatch.setattr(yearly_reporter, "_get_group_name_changes", no_changes)
        monkeypatch.setattr(yearly_reporter, "_get_group_achievements", achievements)
        monkeypatch.setattr(yearly_reporter, "_get_group_statistics", no_stats)
        monkeypatch.setattr(yearly_reporter.asyncio, "sleep", no_sleep)
        messages = asyncio.run(
            yearly_reporter._generate_yearly_report(
                wom_client=object(),
                group_id=7,
                end_date=datetime(2025, 1, 1, 18, 0, tzinfo=timezone.utc),
                log=lambda _message: None,
            )
        )

    assert "XP milestones" in "\n".join(messages)
    with sqlite3.connect(os.environ["WOM_DATABASE_PATH"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM achievements").fetchone()[0] == 1
