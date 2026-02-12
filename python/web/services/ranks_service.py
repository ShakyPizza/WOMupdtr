"""Service layer wrapping rank_utils for web consumption."""

import configparser
import os
from utils.rank_utils import load_ranks, next_rank

_RANKS_INI = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'ranks.ini')


def get_all_players_sorted():
    """Return list of player dicts sorted by EHB descending."""
    ranks = load_ranks()
    players = []
    for username, data in ranks.items():
        players.append({
            "username": username,
            "ehb": data.get("last_ehb", 0),
            "rank": data.get("rank", "Unknown"),
            "discord_name": data.get("discord_name", []),
        })
    players.sort(key=lambda p: p["ehb"], reverse=True)
    return players


def get_player_detail(username):
    """Return detailed player info or None if not found."""
    ranks = load_ranks()
    data = ranks.get(username)
    if not data:
        # Try case-insensitive match
        for key, val in ranks.items():
            if key.lower() == username.lower():
                username = key
                data = val
                break
    if not data:
        return None
    return {
        "username": username,
        "ehb": data.get("last_ehb", 0),
        "rank": data.get("rank", "Unknown"),
        "discord_name": data.get("discord_name", []),
        "next_rank": next_rank(username),
    }


def get_rank_distribution():
    """Return dict of rank_name -> count."""
    ranks = load_ranks()
    dist = {}
    for data in ranks.values():
        rank = data.get("rank", "Unknown")
        dist[rank] = dist.get(rank, 0) + 1
    return dist


def search_players(query):
    """Case-insensitive search by username prefix/substring."""
    if not query:
        return get_all_players_sorted()
    query_lower = query.lower()
    all_players = get_all_players_sorted()
    return [p for p in all_players if query_lower in p["username"].lower()]


def get_rank_thresholds():
    """Read ranks.ini and return ordered list of (lower_bound, upper_bound_or_none, rank_name)."""
    config = configparser.ConfigParser()
    config.read(_RANKS_INI)
    thresholds = []
    for range_key, rank_name in config['Group Ranking'].items():
        if '+' in range_key:
            lower = int(range_key.replace('+', ''))
            thresholds.append({"lower": lower, "upper": None, "name": rank_name})
        else:
            lower, upper = map(int, range_key.split('-'))
            thresholds.append({"lower": lower, "upper": upper, "name": rank_name})
    thresholds.sort(key=lambda t: t["lower"])
    return thresholds
