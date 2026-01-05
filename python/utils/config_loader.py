"""Shared configuration helpers for WOM components.

This module centralizes how configuration values are discovered so the bot can
run in a variety of environments (local development, Docker, or LXC).
Environment variables take precedence over config files, and sensible defaults
are provided where applicable.
"""

from __future__ import annotations

import configparser
import os
from typing import Callable, Optional, TypeVar


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.environ.get("WOM_CONFIG_PATH", os.path.join(BASE_DIR, "config.ini"))
RANKS_PATH = os.environ.get("WOM_RANKS_PATH", os.path.join(BASE_DIR, "ranks.ini"))
RANKS_FILE = os.environ.get(
    "WOM_RANKS_FILE", os.path.join(os.path.dirname(__file__), "player_ranks.json")
)

T = TypeVar("T")


def load_config(path: str = CONFIG_PATH) -> configparser.ConfigParser:
    """Load the bot configuration file if it exists."""

    config = configparser.ConfigParser()
    if os.path.exists(path):
        config.read(path)
    return config


def str_to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _get_config_option(
    config: configparser.ConfigParser, section: str, option: str
) -> Optional[str]:
    if config.has_section(section) and config.has_option(section, option):
        return config.get(section, option)
    return None


def get_config_value(
    section: str,
    option: str,
    env_var: str,
    config: configparser.ConfigParser,
    default: Optional[T] = None,
    cast: Callable[[str], T] = str,
    *,
    required: bool = True,
) -> Optional[T]:
    """Fetch configuration values from environment variables or config files."""

    raw_value = os.environ.get(env_var)
    if raw_value is None:
        raw_value = _get_config_option(config, section, option)

    if raw_value is None:
        raw_value = default

    if raw_value is None:
        if required:
            raise ValueError(
                f"Missing configuration for {section}.{option}. Set {env_var} or "
                f"provide it in {CONFIG_PATH}."
            )
        return None

    try:
        if cast is bool:
            return cast(str_to_bool(str(raw_value)))
        return cast(raw_value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"Invalid value for {section}.{option}: {raw_value}"
        ) from exc
