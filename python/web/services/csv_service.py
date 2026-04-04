"""Service layer for reading EHB CSV history data."""

from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from typing import Any

from utils.log_csv import _resolve_csv_path

logger = logging.getLogger(__name__)


@dataclass
class CsvReadResult:
    """Read result with data payload and optional user-facing error."""

    data: Any
    error: str | None = None


def _read_csv_rows() -> CsvReadResult:
    resolved_path = _resolve_csv_path("ehb_log.csv")
    if not os.path.exists(resolved_path):
        return CsvReadResult([], None)

    try:
        with open(resolved_path, mode="r", newline="", encoding="utf-8") as file_obj:
            return CsvReadResult(list(csv.reader(file_obj)), None)
    except Exception:
        logger.exception("Failed to read EHB CSV log at %s", resolved_path)
        return CsvReadResult([], "EHB history could not be loaded. Check the server logs for details.")


def read_player_ehb_history(username: str) -> CsvReadResult:
    """Return list of {timestamp, ehb} for a specific player, sorted by time."""
    rows_result = _read_csv_rows()
    history = []

    for row in rows_result.data:
        if len(row) < 3:
            continue
        ts = row[0].strip()
        name = row[1].strip()
        try:
            ehb = float(row[2].strip())
        except ValueError:
            continue
        if name.lower() == username.lower():
            history.append({"timestamp": ts, "ehb": ehb})

    history.sort(key=lambda entry: entry["timestamp"])
    return CsvReadResult(history, rows_result.error)


def get_player_ehb_history(username: str) -> list[dict]:
    """Compatibility wrapper returning only the history list."""
    return read_player_ehb_history(username).data


def read_recent_changes(limit: int = 20) -> CsvReadResult:
    """Return the most recent EHB changes across all players."""
    rows_result = _read_csv_rows()
    entries = []

    for row in rows_result.data:
        if len(row) < 3:
            continue
        ts = row[0].strip()
        name = row[1].strip()
        try:
            ehb = float(row[2].strip())
        except ValueError:
            continue
        entries.append({"timestamp": ts, "username": name, "ehb": ehb})

    entries.sort(key=lambda entry: entry["timestamp"], reverse=True)
    return CsvReadResult(entries[:limit], rows_result.error)


def get_recent_changes(limit: int = 20) -> list[dict]:
    """Compatibility wrapper returning only recent changes."""
    return read_recent_changes(limit=limit).data


def read_all_ehb_entries() -> CsvReadResult:
    """Return all CSV entries grouped by player: {username: [{timestamp, ehb}]}."""
    rows_result = _read_csv_rows()
    grouped = {}

    for row in rows_result.data:
        if len(row) < 3:
            continue
        ts = row[0].strip()
        name = row[1].strip()
        try:
            ehb = float(row[2].strip())
        except ValueError:
            continue
        grouped.setdefault(name, []).append({"timestamp": ts, "ehb": ehb})

    for entries in grouped.values():
        entries.sort(key=lambda entry: entry["timestamp"])

    return CsvReadResult(grouped, rows_result.error)


def get_all_ehb_entries() -> dict[str, list[dict]]:
    """Compatibility wrapper returning only grouped entries."""
    return read_all_ehb_entries().data
