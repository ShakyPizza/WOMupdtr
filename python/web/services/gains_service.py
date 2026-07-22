"""Service layer for reading persisted gains-snapshot history (Feature 4).

Reads exclusively from SQLite; never touches the live Wise Old Man API.
"""

from __future__ import annotations

import logging

from utils.database import list_gains_metrics, read_gains_history, read_latest_gains

logger = logging.getLogger(__name__)

_DEFAULT_METRICS = ["overall", "ehb"]


def list_available_metrics() -> list[str]:
    """Return metrics that have stored gains, falling back to sensible defaults."""
    try:
        metrics = list_gains_metrics()
    except Exception:
        logger.exception("Failed to list gains metrics")
        metrics = []
    return metrics or list(_DEFAULT_METRICS)


def read_player_gains_history(username: str, metric: str) -> list[dict]:
    """Return ``[{timestamp, gained}]`` gains history for a player + metric."""
    try:
        return read_gains_history(username, metric)
    except Exception:
        logger.exception("Failed to read gains history for %s/%s", username, metric)
        return []


def read_latest_gains_leaderboard(metric: str, limit: int = 20) -> list[dict]:
    """Return the most recent stored gains leaderboard for a metric."""
    try:
        return read_latest_gains(metric, limit)
    except Exception:
        logger.exception("Failed to read latest gains for %s", metric)
        return []
