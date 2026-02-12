"""FastAPI dependency injection helpers."""

from fastapi import Request

from .services.bot_state import BotState


def get_bot_state(request: Request) -> BotState:
    """Retrieve the shared BotState from the FastAPI application."""
    return request.app.state.bot_state
