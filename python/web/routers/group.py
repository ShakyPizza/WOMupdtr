"""Group router - group statistics."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..services.ranks_service import get_rank_snapshot, get_rank_thresholds
from ..ui import render_template

router = APIRouter()


def _error_headers(error: str | None) -> dict[str, str]:
    return {"X-Data-Error": error} if error else {}


@router.get("/", response_class=HTMLResponse)
async def group_page(request: Request):
    snapshot = get_rank_snapshot()
    thresholds = get_rank_thresholds()
    return render_template(
        request,
        "group_stats.html",
        snapshot=snapshot,
        rank_thresholds=thresholds,
        data_error=snapshot.error,
    )


@router.get("/api/stats")
async def group_stats_api():
    snapshot = get_rank_snapshot()
    return JSONResponse(
        content={
            "total_players": snapshot.total_players,
            "total_ehb": round(snapshot.total_ehb, 2),
            "avg_ehb": round(snapshot.avg_ehb, 2),
            "rank_distribution": snapshot.rank_distribution,
        },
        headers=_error_headers(snapshot.error),
    )
