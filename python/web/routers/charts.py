"""Charts router - chart pages and JSON data APIs."""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ..services.ranks_service import get_all_players_sorted, get_rank_distribution
from ..services.csv_service import get_player_ehb_history

import os

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
)


@router.get("/", response_class=HTMLResponse)
async def charts_page(request: Request):
    players = get_all_players_sorted()
    return templates.TemplateResponse("chart.html", {
        "request": request,
        "players": players,
    })


@router.get("/api/ehb-history")
async def ehb_history_api(player: str = Query(...)):
    history = get_player_ehb_history(player)
    return JSONResponse(content=history)


@router.get("/api/rank-distribution")
async def rank_distribution_api():
    dist = get_rank_distribution()
    return JSONResponse(content=dist)


@router.get("/api/top-players")
async def top_players_api(limit: int = Query(15)):
    players = get_all_players_sorted()[:limit]
    return JSONResponse(content=players)
