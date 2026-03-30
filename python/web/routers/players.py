"""Players router - list, search, detail, history."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..services.csv_service import read_player_ehb_history
from ..services.ranks_service import get_player_detail, get_rank_snapshot, search_players
from ..ui import render_template

router = APIRouter()


def _error_headers(error: str | None) -> dict[str, str]:
    return {"X-Data-Error": error} if error else {}


@router.get("/", response_class=HTMLResponse)
async def player_list(request: Request, q: str = Query(""), sort: str = Query("ehb")):
    snapshot = get_rank_snapshot()
    players = search_players(q, sort=sort, snapshot=snapshot)
    return render_template(
        request,
        "player_list.html",
        players=players,
        query=q,
        sort=sort,
        data_error=snapshot.error,
    )


@router.get("/search", response_class=HTMLResponse)
async def player_search(request: Request, q: str = Query(""), sort: str = Query("ehb")):
    snapshot = get_rank_snapshot()
    players = search_players(q, sort=sort, snapshot=snapshot)
    return render_template(
        request,
        "partials/player_row.html",
        players=players,
        query=q,
        sort=sort,
        data_error=snapshot.error,
    )


@router.get("/{username}", response_class=HTMLResponse)
async def player_detail(request: Request, username: str):
    snapshot = get_rank_snapshot()
    player = get_player_detail(username, snapshot=snapshot)
    history_result = read_player_ehb_history(username)
    if not player:
        return render_template(
            request,
            "player_detail.html",
            player=None,
            history_error=history_result.error,
            data_error=snapshot.error,
            status_code=404,
        )
    return render_template(
        request,
        "player_detail.html",
        player=player,
        history_error=history_result.error,
        data_error=snapshot.error,
    )


@router.get("/{username}/history")
async def player_history(username: str):
    result = read_player_ehb_history(username)
    return JSONResponse(content=result.data, headers=_error_headers(result.error))
