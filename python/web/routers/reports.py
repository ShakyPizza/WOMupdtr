"""Reports router - weekly and yearly reports."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from ..dependencies import get_bot_state
from ..services.bot_state import BotState
from ..services.report_service import get_weekly_report, get_yearly_report
from ..ui import render_template

router = APIRouter()


@router.get("/weekly", response_class=HTMLResponse)
async def weekly_report(request: Request, state: BotState = Depends(get_bot_state)):
    try:
        messages = await get_weekly_report(state)
        report_lines = []
        for message in messages:
            report_lines.extend(message.split("\n"))
        error = None
    except Exception as exc:
        report_lines = []
        error = f"Error generating weekly report: {exc}"

    return render_template(
        request,
        "report_weekly.html",
        report_lines=report_lines,
        data_error=error,
    )


@router.get("/yearly", response_class=HTMLResponse)
async def yearly_report(
    request: Request,
    year: int = Query(None),
    state: BotState = Depends(get_bot_state),
):
    try:
        messages = await get_yearly_report(state, year=year)
        report_lines = []
        for message in messages:
            report_lines.extend(message.split("\n"))
        error = None
    except Exception as exc:
        report_lines = []
        error = f"Error generating yearly report: {exc}"

    return render_template(
        request,
        "report_yearly.html",
        report_lines=report_lines,
        year=year,
        data_error=error,
    )
