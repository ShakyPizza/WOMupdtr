"""Shared template helpers for the WOMupdtr web UI."""

from __future__ import annotations

import os
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .presentation import rank_palette_json, rank_slug

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATES_DIR = os.path.join(_BASE_DIR, "templates")

templates = Jinja2Templates(directory=_TEMPLATES_DIR)
templates.env.filters["rank_slug"] = rank_slug

_NAV_ITEMS = (
    {"key": "dashboard", "label": "Dashboard", "href": "/"},
    {"key": "players", "label": "Players", "href": "/players/"},
    {"key": "reports", "label": "Reports", "href": "/reports/weekly"},
    {"key": "charts", "label": "Charts", "href": "/charts/"},
    {"key": "group", "label": "Group", "href": "/group/"},
    {"key": "admin", "label": "Admin", "href": "/admin/"},
)


def current_page_key(path: str) -> str:
    """Map a request path to its active navigation key."""
    if path == "/":
        return "dashboard"
    for item in _NAV_ITEMS[1:]:
        prefix = item["href"].rstrip("/")
        if path == item["href"] or path.startswith(f"{prefix}/") or path == prefix:
            return item["key"]
    return ""


def build_context(request: Request, **context: Any) -> dict[str, Any]:
    """Return a base template context with global UI metadata."""
    page_key = current_page_key(request.url.path)
    nav_items = [
        {
            **item,
            "active": item["key"] == page_key,
        }
        for item in _NAV_ITEMS
    ]
    return {
        "request": request,
        "current_page": page_key,
        "nav_items": nav_items,
        "rank_palette_json": rank_palette_json(),
        **context,
    }


def render_template(request: Request, template_name: str, status_code: int = 200, **context: Any) -> HTMLResponse:
    """Render a Jinja template with the shared base context."""
    return templates.TemplateResponse(
        template_name,
        build_context(request, **context),
        status_code=status_code,
    )
