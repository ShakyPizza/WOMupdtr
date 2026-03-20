"""Tests for pure / deterministic helper functions in the weekly and yearly reporters."""

import types
from datetime import datetime, timezone

import pytest

from python.weeklyupdater import weekly_reporter
from python.weeklyupdater import yearly_reporter


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
# yearly_reporter — most_recent_year_end / _most_recent_jan1_1200_utc
# ---------------------------------------------------------------------------

def test_most_recent_year_end_returns_current_year_jan1_after_noon():
    """Called on Jan 1 2026 at 13:00 UTC it returns Jan 1 2026 12:00 UTC."""
    now = datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)
    result = yearly_reporter.most_recent_year_end(now)
    assert result == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_most_recent_year_end_returns_previous_year_before_noon_on_jan1():
    """Called on Jan 1 2026 before noon it returns Jan 1 2025 12:00 UTC."""
    now = datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)
    result = yearly_reporter.most_recent_year_end(now)
    assert result == datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_most_recent_year_end_mid_year_returns_current_year_jan1():
    """Called mid-year (e.g. June) it returns Jan 1 of the current year."""
    now = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    result = yearly_reporter.most_recent_year_end(now)
    assert result == datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_most_recent_year_end_raises_for_naive_datetime():
    """Naive datetimes are rejected."""
    now = datetime(2025, 6, 15, 12, 0)  # no tzinfo
    with pytest.raises(ValueError):
        yearly_reporter.most_recent_year_end(now)


# ---------------------------------------------------------------------------
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


def _fake_achievement(player_id, metric_value, dt):
    return types.SimpleNamespace(
        player_id=player_id,
        metric=types.SimpleNamespace(value=metric_value),
        created_at=dt,
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
    assert "Attack" in combined
