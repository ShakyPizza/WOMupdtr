"""Service layer wrapping rank_utils for web consumption."""

from __future__ import annotations

import configparser
import logging
import os
from dataclasses import dataclass

from utils.rank_utils import load_ranks, next_rank

from ..presentation import RANK_ORDER, canonicalize_rank_name

logger = logging.getLogger(__name__)

_RANKS_INI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "ranks.ini")


@dataclass
class RankSnapshot:
    """Normalized rank data used by web routes and templates."""

    players: list[dict]
    rank_distribution: dict[str, int]
    total_players: int
    total_ehb: float
    avg_ehb: float
    error: str | None = None


def _build_player(username: str, data: dict) -> dict:
    return {
        "username": username,
        "ehb": data.get("last_ehb", 0),
        "rank": canonicalize_rank_name(data.get("rank", "Unknown")),
    }


def get_rank_snapshot() -> RankSnapshot:
    """Return a normalized snapshot of rank data for a single request."""
    try:
        ranks = load_ranks()
    except Exception:
        logger.exception("Failed to load player ranks for web request")
        return RankSnapshot(
            players=[],
            rank_distribution={},
            total_players=0,
            total_ehb=0,
            avg_ehb=0,
            error="Rank data could not be loaded. Check the server logs for details.",
        )

    players = [_build_player(username, data) for username, data in ranks.items()]
    players.sort(key=lambda player: (-player["ehb"], player["username"].lower()))

    rank_distribution = {}
    for player in players:
        rank_distribution[player["rank"]] = rank_distribution.get(player["rank"], 0) + 1
    rank_distribution = {
        rank_name: rank_distribution[rank_name]
        for rank_name in RANK_ORDER
        if rank_name in rank_distribution
    } | {
        rank_name: count
        for rank_name, count in rank_distribution.items()
        if rank_name not in RANK_ORDER
    }

    total_ehb = sum(player["ehb"] for player in players)
    total_players = len(players)

    return RankSnapshot(
        players=players,
        rank_distribution=rank_distribution,
        total_players=total_players,
        total_ehb=total_ehb,
        avg_ehb=(total_ehb / total_players) if total_players else 0,
    )


def get_all_players_sorted(snapshot: RankSnapshot | None = None) -> list[dict]:
    """Return list of player dicts sorted by EHB descending."""
    return list((snapshot or get_rank_snapshot()).players)


def get_player_detail(username: str, snapshot: RankSnapshot | None = None) -> dict | None:
    """Return detailed player info or None if not found."""
    players = (snapshot or get_rank_snapshot()).players
    for player in players:
        if player["username"].lower() == username.lower():
            return {
                **player,
                "next_rank": next_rank(player["username"]),
            }
    return None


def get_rank_distribution(snapshot: RankSnapshot | None = None) -> dict[str, int]:
    """Return dict of rank_name -> count."""
    return dict((snapshot or get_rank_snapshot()).rank_distribution)


def search_players(query: str, sort: str = "ehb", snapshot: RankSnapshot | None = None) -> list[dict]:
    """Case-insensitive search by username prefix/substring with optional sorting."""
    players = list((snapshot or get_rank_snapshot()).players)
    query_lower = query.lower().strip()
    if query_lower:
        players = [player for player in players if query_lower in player["username"].lower()]

    if sort == "name":
        players.sort(key=lambda player: player["username"].lower())
    elif sort == "rank":
        rank_positions = {name: index for index, name in enumerate(RANK_ORDER)}
        players.sort(key=lambda player: (rank_positions.get(player["rank"], len(RANK_ORDER)), -player["ehb"]))
    else:
        players.sort(key=lambda player: (-player["ehb"], player["username"].lower()))

    return players


def get_rank_thresholds() -> list[dict]:
    """Read ranks.ini and return ordered list of threshold dicts."""
    config = configparser.ConfigParser()
    config.read(_RANKS_INI)
    thresholds = []
    for range_key, rank_name in config["Group Ranking"].items():
        if "+" in range_key:
            lower = int(range_key.replace("+", ""))
            thresholds.append({
                "lower": lower,
                "upper": None,
                "name": canonicalize_rank_name(rank_name),
            })
        else:
            lower, upper = map(int, range_key.split("-"))
            thresholds.append({
                "lower": lower,
                "upper": upper,
                "name": canonicalize_rank_name(rank_name),
            })
    thresholds.sort(key=lambda threshold: threshold["lower"])
    return thresholds
