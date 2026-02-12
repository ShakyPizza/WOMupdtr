"""Group router - group statistics."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ..services.ranks_service import get_all_players_sorted, get_rank_distribution, get_rank_thresholds

import os

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
)


@router.get("/", response_class=HTMLResponse)
async def group_page(request: Request):
    players = get_all_players_sorted()
    rank_dist = get_rank_distribution()
    thresholds = get_rank_thresholds()
    total_ehb = sum(p["ehb"] for p in players)
    avg_ehb = total_ehb / len(players) if players else 0
    return templates.TemplateResponse("group_stats.html", {
        "request": request,
        "players": players,
        "rank_distribution": rank_dist,
        "total_ehb": total_ehb,
        "avg_ehb": avg_ehb,
        "rank_thresholds": thresholds,
    })


@router.get("/api/stats")
async def group_stats_api():
    players = get_all_players_sorted()
    rank_dist = get_rank_distribution()
    total_ehb = sum(p["ehb"] for p in players)
    avg_ehb = total_ehb / len(players) if players else 0
    return JSONResponse(content={
        "total_players": len(players),
        "total_ehb": round(total_ehb, 2),
        "avg_ehb": round(avg_ehb, 2),
        "rank_distribution": rank_dist,
    })
