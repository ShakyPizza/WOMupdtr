"""Admin router - bot control, logs, config."""

from __future__ import annotations

import html
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from datetime import datetime, timedelta, timezone

from ..dependencies import get_bot_state
from ..services.bot_state import BotState
from ..ui import render_template
from utils.api_usage import tracker as api_usage_tracker
from utils.database import count_api_calls_since, read_recent_api_calls

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def admin_page(request: Request, state: BotState = Depends(get_bot_state)):
    return render_template(request, "admin.html", bot_state=state)


@router.post("/force-check", response_class=HTMLResponse)
async def force_check(state: BotState = Depends(get_bot_state)):
    if state.check_for_rank_changes and hasattr(state.check_for_rank_changes, "__call__"):
        try:
            await state.check_for_rank_changes()
            return HTMLResponse('<p class="feedback success">Rank check triggered successfully.</p>')
        except Exception:
            logger.exception("Error while triggering rank check")
            return HTMLResponse(
                '<p class="feedback error">An internal error occurred while triggering rank check.</p>'
            )
    return HTMLResponse('<p class="feedback error">Rank check function not available.</p>')


@router.post("/refresh-group", response_class=HTMLResponse)
async def refresh_group(state: BotState = Depends(get_bot_state)):
    if state.refresh_group_data:
        try:
            message = await state.refresh_group_data()
            safe_message = html.escape(message)
            return HTMLResponse(f'<p class="feedback success">{safe_message}</p>')
        except Exception:
            logger.exception("Error while refreshing group data")
            return HTMLResponse(
                '<p class="feedback error">An internal error occurred while refreshing group data.</p>'
            )
    return HTMLResponse('<p class="feedback error">Refresh function not available.</p>')


@router.get("/logs", response_class=HTMLResponse)
async def get_logs(request: Request, state: BotState = Depends(get_bot_state)):
    log_lines = list(state.log_buffer)[-100:]
    return render_template(request, "partials/log_feed.html", log_lines=log_lines)


@router.get("/api-usage", response_class=HTMLResponse)
async def get_api_usage(request: Request):
    _TS_FMT = "%Y-%m-%d %H:%M:%S"
    now = datetime.now(timezone.utc)
    hour_ago = (now - timedelta(hours=1)).strftime(_TS_FMT)
    day_ago = (now - timedelta(days=1)).strftime(_TS_FMT)

    return render_template(
        request,
        "partials/api_usage_feed.html",
        breaker=api_usage_tracker.breaker_status(),
        calls_last_minute=api_usage_tracker.calls_in_last(60),
        calls_last_hour=count_api_calls_since(hour_ago),
        calls_last_day=count_api_calls_since(day_ago),
        recent_calls=read_recent_api_calls(limit=25),
        rate_limit_per_minute=api_usage_tracker.rate_limit_per_minute,
    )


@router.get("/status")
async def bot_status(state: BotState = Depends(get_bot_state)):
    return JSONResponse(
        content={
            "bot_started_at": state.bot_started_at.isoformat() if state.bot_started_at else None,
            "last_rank_check": state.last_rank_check.isoformat() if state.last_rank_check else None,
            "last_group_refresh": state.last_group_refresh.isoformat() if state.last_group_refresh else None,
            "check_interval": state.check_interval,
            "silent": state.silent,
            "debug": state.debug,
            "post_to_discord": state.post_to_discord,
        }
    )


@router.post("/config", response_class=HTMLResponse)
async def update_config(request: Request, state: BotState = Depends(get_bot_state)):
    form = await request.form()
    state.silent = "silent" in form
    state.debug = "debug" in form
    return HTMLResponse('<p class="feedback success">Configuration updated.</p>')
