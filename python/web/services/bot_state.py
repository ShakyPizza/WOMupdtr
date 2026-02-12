"""Shared state container between the Discord bot and the FastAPI web server."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


@dataclass
class BotState:
    """Mutable state shared between the Discord bot and web interface.

    Created once at startup and passed to both the Discord bot event loop
    and the FastAPI application via ``app.state``.
    """

    # Core client references (set during startup)
    wom_client: Any = None
    discord_client: Any = None
    group_id: int = 0
    group_passcode: str = ""

    # Function references injected from WOM.py
    get_rank: Optional[Callable] = None
    list_all_members_and_ranks: Optional[Callable] = None
    check_for_rank_changes: Optional[Callable] = None
    refresh_group_data: Optional[Callable] = None
    log_func: Optional[Callable] = None

    # Runtime config (readable/writable from admin panel)
    check_interval: int = 300
    post_to_discord: bool = True
    silent: bool = False
    debug: bool = False

    # Runtime telemetry
    log_buffer: deque = field(default_factory=lambda: deque(maxlen=500))
    last_rank_check: Optional[datetime] = None
    last_group_refresh: Optional[datetime] = None
    bot_started_at: Optional[datetime] = None
