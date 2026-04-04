"""Shared presentation metadata for the WOMupdtr web UI."""

from __future__ import annotations

import json

RANK_ORDER = [
    "Goblin",
    "Opal",
    "Sapphire",
    "Emerald",
    "Red Topaz",
    "Ruby",
    "Diamond",
    "Dragonstone",
    "Onyx",
    "Zenyte",
    "Unknown",
]

RANK_COLORS = {
    "Goblin": "#567d32",
    "Opal": "#a6d2dc",
    "Sapphire": "#3a79d9",
    "Emerald": "#3fae72",
    "Red Topaz": "#d96249",
    "Ruby": "#c8416c",
    "Diamond": "#d4f4ff",
    "Dragonstone": "#7260b9",
    "Onyx": "#282a31",
    "Zenyte": "#f0b93a",
    "Unknown": "#69707d",
}

_RANK_LOOKUP = {name.lower(): name for name in RANK_ORDER}


def canonicalize_rank_name(rank_name: str | None) -> str:
    """Return the canonical display name for a rank."""
    if not rank_name:
        return "Unknown"
    normalized = " ".join(str(rank_name).strip().split())
    return _RANK_LOOKUP.get(normalized.lower(), normalized.title())


def rank_slug(rank_name: str | None) -> str:
    """Return a CSS-safe slug for a rank."""
    return canonicalize_rank_name(rank_name).lower().replace(" ", "-")


def rank_palette_json() -> str:
    """Return the canonical rank palette as JSON for the frontend."""
    return json.dumps(RANK_COLORS)
