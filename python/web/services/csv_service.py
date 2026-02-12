"""Service layer for reading EHB CSV history data."""

import csv
import os

from utils.log_csv import _resolve_csv_path


def get_player_ehb_history(username):
    """Return list of {timestamp, ehb} for a specific player, sorted by time."""
    resolved_path = _resolve_csv_path("ehb_log.csv")
    if not os.path.exists(resolved_path):
        return []

    history = []
    try:
        with open(resolved_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
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
    except Exception:
        return []

    history.sort(key=lambda e: e["timestamp"])
    return history


def get_recent_changes(limit=20):
    """Return the most recent EHB changes across all players."""
    resolved_path = _resolve_csv_path("ehb_log.csv")
    if not os.path.exists(resolved_path):
        return []

    entries = []
    try:
        with open(resolved_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 3:
                    continue
                ts = row[0].strip()
                name = row[1].strip()
                try:
                    ehb = float(row[2].strip())
                except ValueError:
                    continue
                entries.append({"timestamp": ts, "username": name, "ehb": ehb})
    except Exception:
        return []

    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return entries[:limit]


def get_all_ehb_entries():
    """Return all CSV entries grouped by player: {username: [{timestamp, ehb}]}."""
    resolved_path = _resolve_csv_path("ehb_log.csv")
    if not os.path.exists(resolved_path):
        return {}

    grouped = {}
    try:
        with open(resolved_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 3:
                    continue
                ts = row[0].strip()
                name = row[1].strip()
                try:
                    ehb = float(row[2].strip())
                except ValueError:
                    continue
                grouped.setdefault(name, []).append({"timestamp": ts, "ehb": ehb})
    except Exception:
        return {}

    for entries in grouped.values():
        entries.sort(key=lambda e: e["timestamp"])

    return grouped
