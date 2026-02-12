"""Service layer for generating reports via the web interface."""

from datetime import datetime, timezone

from weeklyupdater import (
    generate_weekly_report_messages,
    generate_yearly_report_messages,
    most_recent_week_end,
    most_recent_year_end,
)


async def get_weekly_report(bot_state):
    """Generate the most recent weekly report as a list of text chunks."""
    now = datetime.now(timezone.utc)
    end_date = most_recent_week_end(now)

    def log(msg):
        if bot_state.log_func:
            bot_state.log_func(msg)

    messages = await generate_weekly_report_messages(
        wom_client=bot_state.wom_client,
        group_id=bot_state.group_id,
        end_date=end_date,
        log=log,
    )
    return messages


async def get_yearly_report(bot_state, year=None):
    """Generate a yearly report. If year is None, uses the most recent completed year."""
    now = datetime.now(timezone.utc)

    if year is not None:
        from weeklyupdater.yearly_reporter import _year_boundary_1200_utc
        end_date = _year_boundary_1200_utc(year + 1)
    else:
        end_date = most_recent_year_end(now)

    def log(msg):
        if bot_state.log_func:
            bot_state.log_func(msg)

    messages = await generate_yearly_report_messages(
        wom_client=bot_state.wom_client,
        group_id=bot_state.group_id,
        end_date=end_date,
        log=log,
    )
    return messages
