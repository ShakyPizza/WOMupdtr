"""Players router - list, search, detail, history."""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ..dependencies import get_bot_state
from ..services.bot_state import BotState
from ..services.ranks_service import get_all_players_sorted, get_player_detail, search_players
from ..services.csv_service import get_player_ehb_history

import os

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
)


@router.get("/", response_class=HTMLResponse)
async def player_list(request: Request):
    players = get_all_players_sorted()
    return templates.TemplateResponse("player_list.html", {
        "request": request,
        "players": players,
        "query": "",
    })


@router.get("/search", response_class=HTMLResponse)
async def player_search(request: Request, q: str = Query("")):
    players = search_players(q)
    return templates.TemplateResponse("partials/player_row.html", {
        "request": request,
        "players": players,
    })


@router.get("/{username}", response_class=HTMLResponse)
async def player_detail(request: Request, username: str):
    player = get_player_detail(username)
    if not player:
        return HTMLResponse("<h2>Player not found</h2>", status_code=404)
    return templates.TemplateResponse("player_detail.html", {
        "request": request,
        "player": player,
    })


@router.get("/{username}/history")
async def player_history(username: str):
    history = get_player_ehb_history(username)
    return JSONResponse(content=history)
