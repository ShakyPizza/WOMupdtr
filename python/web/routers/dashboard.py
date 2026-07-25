"""Dashboard router - main landing page."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse

from ..dependencies import get_bot_state
from ..services.bot_state import BotState
from ..services.csv_service import read_recent_changes
from ..services.ranks_service import get_rank_snapshot
from ..ui import render_template

router = APIRouter()
_ROBOTS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "robots.txt")


@router.get("/robots.txt", response_class=FileResponse, include_in_schema=False)
async def robots_txt():
    return FileResponse(_ROBOTS_PATH, media_type="text/plain")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, state: BotState = Depends(get_bot_state)):
    snapshot = get_rank_snapshot()
    recent_result = read_recent_changes(limit=10)
    errors = [error for error in (snapshot.error, recent_result.error) if error]
    return render_template(
        request,
        "dashboard.html",
        snapshot=snapshot,
        recent_changes=recent_result.data,
        bot_state=state,
        data_error=" ".join(errors) if errors else None,
    )
