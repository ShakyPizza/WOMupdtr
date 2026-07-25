import json
import os
import configparser
from .database import read_player_snapshots, upsert_players
from .log_csv import load_latest_ehb_from_csv

# Legacy JSON snapshot retained only as a one-time migration source.
RANKS_FILE = os.path.join(os.path.dirname(__file__), 'player_ranks.json')
RANKS_INI = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ranks.ini')

# Section names inside ranks.ini for each tracked metric.
EHB_SECTION = "Group Ranking"
EHP_SECTION = "Skilling Ranking"

_BOOTSTRAPPED_FROM_CSV = False


def get_rank_thresholds(section=EHB_SECTION, ranks_file=None):
    """Return sorted ``[(lower, upper_or_None, rank_name), ...]`` for a ranks.ini section.

    A ``"1500+"`` key becomes ``(1500, None, name)`` (open-ended); a ``"10-50"``
    key becomes ``(10, 50, name)``. Results are sorted by lower bound. Unknown
    sections return an empty list.
    """
    config = configparser.ConfigParser()
    config.read(ranks_file or RANKS_INI)
    if not config.has_section(section):
        return []

    thresholds = []
    for range_key, rank_name in config[section].items():
        if '+' in range_key:
            lower_bound = int(range_key.replace('+', ''))
            thresholds.append((lower_bound, None, rank_name))
        else:
            lower_bound, upper_bound = map(int, range_key.split('-'))
            thresholds.append((lower_bound, upper_bound, rank_name))
    thresholds.sort(key=lambda item: item[0])
    return thresholds


def get_rank_for_value(value, section=EHB_SECTION, ranks_file=None):
    """Return the rank name for ``value`` using the given ranks.ini section.

    Boundary semantics: ``lower <= value < upper`` for ranges, ``value >= lower``
    for open-ended ``"+"`` tiers. Falls back to ``"Unknown"``.
    """
    try:
        for lower_bound, upper_bound, rank_name in get_rank_thresholds(section, ranks_file):
            if upper_bound is None:
                if value >= lower_bound:
                    return rank_name
            elif lower_bound <= value < upper_bound:
                return rank_name
    except Exception as e:
        print(f"Error reading ranks.ini: {e}")
    return "Unknown"


def _get_rank_for_ehb(ehb, ranks_file=None):
    """Return rank name for an EHB value using ranks.ini thresholds."""
    return get_rank_for_value(ehb, EHB_SECTION, ranks_file)


def get_ehp_rank(ehp, ranks_file=None):
    """Return the skilling rank name for an EHP value."""
    return get_rank_for_value(ehp, EHP_SECTION, ranks_file)


def _bootstrap_ranks_from_csv():
    """Seed ranks data from ehb_log.csv when JSON storage is missing/corrupt."""
    global _BOOTSTRAPPED_FROM_CSV
    ehb_map = load_latest_ehb_from_csv()
    if not ehb_map:
        return {}
    _BOOTSTRAPPED_FROM_CSV = True
    ranks_data = {}
    for username, ehb in ehb_map.items():
        ranks_data[username] = {
            "last_ehb": ehb,
            "rank": _get_rank_for_ehb(ehb),
        }
    print("Loaded ranks from ehb_log.csv.")
    return ranks_data

def load_ranks():
    """Load rank snapshots from SQLite, importing legacy storage when empty."""
    persisted = read_player_snapshots()
    if persisted:
        return persisted

    if os.path.exists(RANKS_FILE):
        try:
            with open(RANKS_FILE, 'r') as f:
                legacy_data = json.load(f)

        except (json.JSONDecodeError, ValueError):
            print(f"Error: {RANKS_FILE} is empty or corrupted. Trying legacy CSV.")
        else:
            if legacy_data:
                sanitized_data = {
                    username: _sanitize_player_entry(pdata)
                    for username, pdata in legacy_data.items()
                }
                upsert_players(sanitized_data)
                print(f"Imported legacy rank snapshots from {RANKS_FILE} into SQLite.")
                return sanitized_data

    legacy_data = _bootstrap_ranks_from_csv()
    if legacy_data:
        upsert_players(legacy_data)
        print("Imported legacy EHB snapshots from CSV into SQLite.")
    return legacy_data

def _sanitize_player_entry(pdata):
    """Return the supported rank fields for SQLite persistence."""
    pdata = pdata or {}
    entry = {
        "last_ehb": pdata.get("last_ehb", 0),
        "rank": pdata.get("rank", "Unknown"),
    }
    if "last_ehp" in pdata or "ehp_rank" in pdata:
        entry["last_ehp"] = pdata.get("last_ehp", 0)
        entry["ehp_rank"] = pdata.get("ehp_rank", "Unknown")
    if "total_xp" in pdata:
        total_xp = pdata.get("total_xp")
        entry["total_xp"] = int(total_xp) if total_xp is not None else None
    return entry


def merge_manual_rank_update(last_data: dict, ehb: float, rank: str) -> dict:
    """Return a manual EHB update without discarding unrelated player state."""
    entry = dict(last_data or {})
    entry["last_ehb"] = ehb
    entry["rank"] = rank
    return entry


def save_ranks(data):
    """Persist the latest sanitized rank snapshot to SQLite."""
    sanitized_data = {
        username: _sanitize_player_entry(pdata)
        for username, pdata in data.items()
    }

    upsert_players(sanitized_data)

def _next_rank_for(current_rank, section, unit_label):
    """Return the next-rank description for a current rank within a ranks section."""
    rank_thresholds = [(lower, name) for lower, _upper, name in get_rank_thresholds(section)]

    if not rank_thresholds:
        return "Unknown"

    for i, (threshold, rank_name) in enumerate(rank_thresholds):
        if current_rank != rank_name:
            continue
        if i + 1 == len(rank_thresholds):
            return "Max Rank Achieved 👑"
        next_rank_name = rank_thresholds[i + 1][1]
        next_threshold = rank_thresholds[i + 1][0]
        return f"{next_rank_name} at {next_threshold} {unit_label}"

    return "Unknown"


def compute_member_update(
    last_data,
    ehb,
    rank,
    ehp=None,
    ehp_rank=None,
    track_ehp=False,
    total_xp=None,
):
    """Merge new EHB/EHP/total-XP values into a member's stored entry (pure).

    Returns a dict with the merged ``entry`` plus decision flags the caller uses
    to drive side effects (Discord notifications, CSV/DB logging). EHB and EHP are
    evaluated independently so an EHP-only rank-up is never swallowed by a flat EHB.
    """
    last_data = last_data or {}
    entry = dict(last_data)

    last_ehb = last_data.get("last_ehb", 0)
    last_rank = last_data.get("rank", "Unknown")

    ehb_increase = ehb > last_ehb
    if ehb_increase:
        entry["last_ehb"] = ehb
        entry["rank"] = rank
    elif rank != last_rank:
        entry["rank"] = rank

    ehp_increase = False
    last_ehp_rank = last_data.get("ehp_rank", "Unknown")
    if track_ehp and ehp is not None:
        last_ehp = last_data.get("last_ehp", 0)
        ehp_increase = ehp > last_ehp
        if ehp_increase or ehp_rank != last_ehp_rank:
            entry["last_ehp"] = ehp
            entry["ehp_rank"] = ehp_rank

    if total_xp is not None:
        entry["total_xp"] = int(total_xp)

    return {
        "entry": entry,
        "ehb_increase": ehb_increase,
        "ehb_old_rank": last_rank,
        "ehp_increase": ehp_increase,
        "ehp_old_rank": last_ehp_rank,
    }


def next_rank(username):
    """Returns the next rank for a given player based on their current EHB."""
    try:
        ranks_data = load_ranks()
        user_data = ranks_data.get(username)

        if not user_data:
            return "Unknown"  # Return 'Unknown' if the user is not found

        current_rank = user_data.get("rank", "Unknown")
        return _next_rank_for(current_rank, EHB_SECTION, "EHB")

    except Exception as e:
        print(f"Error in next_rank function: {e}")
        return "Error fetching next rank"


def next_rank_ehp(username):
    """Returns the next skilling rank for a given player based on their current EHP."""
    try:
        ranks_data = load_ranks()
        user_data = ranks_data.get(username)

        if not user_data:
            return "Unknown"

        current_rank = user_data.get("ehp_rank", "Unknown")
        return _next_rank_for(current_rank, EHP_SECTION, "EHP")

    except Exception as e:
        print(f"Error in next_rank_ehp function: {e}")
        return "Error fetching next rank"
