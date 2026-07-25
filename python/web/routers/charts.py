"""Charts router - chart pages and JSON data APIs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from utils.database import read_player_ehp_history

from ..services.csv_service import read_player_ehb_history
from ..services.gains_service import list_available_metrics, read_player_gains_history
from ..services.ranks_service import get_rank_snapshot
from ..ui import render_template

router = APIRouter()
logger = logging.getLogger(__name__)


def _error_headers(error: str | None) -> dict[str, str]:
    return {"X-Data-Error": error} if error else {}


def _history_response(data: list[dict], error: str | None = None) -> JSONResponse:
    return JSONResponse(
        content=data,
        headers=_error_headers(error),
        status_code=503 if error else 200,
    )


def _read_database_history(reader, error_message: str, *args) -> JSONResponse:
    try:
        return _history_response(reader(*args))
    except Exception:
        logger.exception("Failed to read chart history data")
        return _history_response([], error_message)


@router.get("/", response_class=HTMLResponse)
async def charts_page(request: Request):
    snapshot = get_rank_snapshot()
    return render_template(
        request,
        "chart.html",
        players=snapshot.players,
        ehp_players=[player for player in snapshot.players if player["ehp_tracked"]],
        gains_metrics=list_available_metrics(),
        data_error=snapshot.error,
    )


@router.get("/api/ehb-history")
async def ehb_history_api(player: str = Query(...)):
    result = read_player_ehb_history(player)
    return _history_response(result.data, result.error)


@router.get("/api/ehp-history")
async def ehp_history_api(player: str = Query(...)):
    return _read_database_history(
        read_player_ehp_history,
        "EHP history could not be loaded. Check the server logs for details.",
        player,
    )


@router.get("/api/gains-history")
async def gains_history_api(player: str = Query(...), metric: str = Query("overall")):
    return _read_database_history(
        read_player_gains_history,
        "Gains history could not be loaded. Check the server logs for details.",
        player,
        metric,
    )


@router.get("/api/rank-distribution")
async def rank_distribution_api():
    snapshot = get_rank_snapshot()
    return JSONResponse(content=snapshot.rank_distribution, headers=_error_headers(snapshot.error))


@router.get("/api/top-players")
async def top_players_api(limit: int = Query(15, ge=1, le=50)):
    snapshot = get_rank_snapshot()
    return JSONResponse(content=snapshot.players[:limit], headers=_error_headers(snapshot.error))
