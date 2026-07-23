"""Charts router - chart pages and JSON data APIs."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from utils.database import read_player_ehp_history

from ..services.csv_service import read_player_ehb_history
from ..services.gains_service import list_available_metrics, read_player_gains_history
from ..services.ranks_service import get_rank_snapshot
from ..ui import render_template

router = APIRouter()


def _error_headers(error: str | None) -> dict[str, str]:
    return {"X-Data-Error": error} if error else {}


@router.get("/", response_class=HTMLResponse)
async def charts_page(request: Request):
    snapshot = get_rank_snapshot()
    return render_template(
        request,
        "chart.html",
        players=snapshot.players,
        gains_metrics=list_available_metrics(),
        data_error=snapshot.error,
    )


@router.get("/api/ehb-history")
async def ehb_history_api(player: str = Query(...)):
    result = read_player_ehb_history(player)
    return JSONResponse(content=result.data, headers=_error_headers(result.error))


@router.get("/api/ehp-history")
async def ehp_history_api(player: str = Query(...)):
    return JSONResponse(content=read_player_ehp_history(player))


@router.get("/api/gains-history")
async def gains_history_api(player: str = Query(...), metric: str = Query("overall")):
    return JSONResponse(content=read_player_gains_history(player, metric))


@router.get("/api/rank-distribution")
async def rank_distribution_api():
    snapshot = get_rank_snapshot()
    return JSONResponse(content=snapshot.rank_distribution, headers=_error_headers(snapshot.error))


@router.get("/api/top-players")
async def top_players_api(limit: int = Query(15, ge=1, le=50)):
    snapshot = get_rank_snapshot()
    return JSONResponse(content=snapshot.players[:limit], headers=_error_headers(snapshot.error))
