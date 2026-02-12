"""Dashboard router - main landing page."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..dependencies import get_bot_state
from ..services.bot_state import BotState
from ..services.ranks_service import get_all_players_sorted, get_rank_distribution
from ..services.csv_service import get_recent_changes

import os

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, state: BotState = Depends(get_bot_state)):
    players = get_all_players_sorted()
    rank_dist = get_rank_distribution()
    recent = get_recent_changes(limit=20)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "players": players,
        "rank_distribution": rank_dist,
        "recent_changes": recent,
        "bot_state": state,
        "player_count": len(players),
    })
