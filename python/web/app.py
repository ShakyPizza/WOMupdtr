"""FastAPI application factory for the WOMupdtr web interface."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .services.bot_state import BotState

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app(state: BotState, host: str = "0.0.0.0", port: int = 8080, log_func=None) -> FastAPI:
    """Build and return the configured FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.bot_state = state
        display_host = "localhost" if host in ("0.0.0.0", "") else host
        url = f"http://{display_host}:{port}"
        if log_func:
            log_func(f"Web UI is up and running at {url}")
        else:
            print(f"Web UI is up and running at {url}")
        yield

    app = FastAPI(title="WOMupdtr Dashboard", lifespan=lifespan)

    # Static files
    static_dir = os.path.join(_BASE_DIR, "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Register routers (imported here to avoid circular imports)
    from .routers import admin, charts, dashboard, group, players, reports

    app.include_router(dashboard.router)
    app.include_router(players.router, prefix="/players", tags=["players"])
    app.include_router(reports.router, prefix="/reports", tags=["reports"])
    app.include_router(charts.router, prefix="/charts", tags=["charts"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    app.include_router(group.router, prefix="/group", tags=["group"])

    return app
