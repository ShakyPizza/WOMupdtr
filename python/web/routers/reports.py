"""Reports router - weekly and yearly reports."""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..dependencies import get_bot_state
from ..services.bot_state import BotState
from ..services.report_service import get_weekly_report, get_yearly_report

import os

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
)


@router.get("/weekly", response_class=HTMLResponse)
async def weekly_report(request: Request, state: BotState = Depends(get_bot_state)):
    try:
        messages = await get_weekly_report(state)
        report_lines = []
        for msg in messages:
            report_lines.extend(msg.split("\n"))
    except Exception as e:
        report_lines = [f"Error generating weekly report: {e}"]
    return templates.TemplateResponse("report_weekly.html", {
        "request": request,
        "report_lines": report_lines,
    })


@router.get("/yearly", response_class=HTMLResponse)
async def yearly_report(
    request: Request,
    year: int = Query(None),
    state: BotState = Depends(get_bot_state),
):
    try:
        messages = await get_yearly_report(state, year=year)
        report_lines = []
        for msg in messages:
            report_lines.extend(msg.split("\n"))
    except Exception as e:
        report_lines = [f"Error generating yearly report: {e}"]
    return templates.TemplateResponse("report_yearly.html", {
        "request": request,
        "report_lines": report_lines,
        "year": year,
    })
