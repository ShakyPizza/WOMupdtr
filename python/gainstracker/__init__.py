"""Persisted gains-snapshot tracking (Feature 4)."""

from .gains_snapshotter import (
    build_gains_lines,
    collect_gains_leaderboard,
    resolve_metric,
    snapshot_gains_once,
    start_gains_snapshotter,
)

__all__ = [
    "build_gains_lines",
    "collect_gains_leaderboard",
    "resolve_metric",
    "snapshot_gains_once",
    "start_gains_snapshotter",
]
