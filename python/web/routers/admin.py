"""Admin router - bot control, logs, config."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ..dependencies import get_bot_state
from ..services.bot_state import BotState

import os

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
)


@router.get("/", response_class=HTMLResponse)
async def admin_page(request: Request, state: BotState = Depends(get_bot_state)):
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "bot_state": state,
    })


@router.post("/force-check", response_class=HTMLResponse)
async def force_check(state: BotState = Depends(get_bot_state)):
    if state.check_for_rank_changes and hasattr(state.check_for_rank_changes, '__call__'):
        try:
            await state.check_for_rank_changes()
            return HTMLResponse('<p class="success">Rank check triggered successfully.</p>')
        except Exception as e:
            return HTMLResponse(f'<p class="error">Error: {e}</p>')
    return HTMLResponse('<p class="error">Rank check function not available.</p>')


@router.post("/refresh-group", response_class=HTMLResponse)
async def refresh_group(state: BotState = Depends(get_bot_state)):
    if state.refresh_group_data:
        try:
            msg = await state.refresh_group_data()
            return HTMLResponse(f'<p>{msg}</p>')
        except Exception as e:
            return HTMLResponse(f'<p class="error">Error: {e}</p>')
    return HTMLResponse('<p class="error">Refresh function not available.</p>')


@router.get("/logs", response_class=HTMLResponse)
async def get_logs(request: Request, state: BotState = Depends(get_bot_state)):
    log_lines = list(state.log_buffer)[-100:]  # Last 100 lines
    return templates.TemplateResponse("partials/log_feed.html", {
        "request": request,
        "log_lines": log_lines,
    })


@router.get("/status")
async def bot_status(state: BotState = Depends(get_bot_state)):
    return JSONResponse(content={
        "bot_started_at": state.bot_started_at.isoformat() if state.bot_started_at else None,
        "last_rank_check": state.last_rank_check.isoformat() if state.last_rank_check else None,
        "last_group_refresh": state.last_group_refresh.isoformat() if state.last_group_refresh else None,
        "check_interval": state.check_interval,
        "silent": state.silent,
        "debug": state.debug,
        "post_to_discord": state.post_to_discord,
    })


@router.post("/config", response_class=HTMLResponse)
async def update_config(request: Request, state: BotState = Depends(get_bot_state)):
    form = await request.form()
    state.silent = "silent" in form
    state.debug = "debug" in form
    return HTMLResponse('<p class="success">Configuration updated.</p>')
