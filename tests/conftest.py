"""Shared fixtures for the WOMupdtr test suite."""

import configparser
import csv
import json
import os
import sys
import types

import pytest

# Allow importing the 'python' package from the repo root
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_PYTHON_DIR = os.path.join(_REPO_ROOT, "python")

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Also expose python/ directly so that absolute imports inside web services
# (e.g. ``from utils.rank_utils import load_ranks``) resolve correctly.
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

# Stub requests before any module import that triggers baserow_connect
_requests_stub = types.ModuleType("requests")
setattr(_requests_stub, "post", lambda *a, **k: None)
setattr(_requests_stub, "get", lambda *a, **k: None)
setattr(_requests_stub, "patch", lambda *a, **k: None)
sys.modules.setdefault("requests", _requests_stub)


@pytest.fixture
def sample_players():
    """Three players at different EHB / rank levels."""
    return {
        "goblin_gaz": {"last_ehb": 5.0, "rank": "Goblin", "discord_name": ["Gaz#1234"]},
        "silver_sam": {"last_ehb": 150.0, "rank": "Silver", "discord_name": ["Sam#5678"]},
        "zenyte_zoe": {"last_ehb": 1600.0, "rank": "Zenyte", "discord_name": []},
    }


@pytest.fixture
def ranks_ini_file(tmp_path):
    """Write a ranks.ini with known thresholds to tmp_path and return the path."""
    ranks_ini = tmp_path / "ranks.ini"
    ranks_ini.write_text(
        "[Group Ranking]\n"
        "0-10 = Goblin\n"
        "10-50 = Opal\n"
        "50-120 = Sapphire\n"
        "120-250 = Emerald\n"
        "250-400 = Red Topaz\n"
        "400-550 = Ruby\n"
        "550-750 = Diamond\n"
        "750-1000 = Dragonstone\n"
        "1000-1500 = Onyx\n"
        "1500+ = Zenyte\n"
    )
    return ranks_ini


@pytest.fixture
def tmp_ranks_ini(tmp_path, monkeypatch):
    """Write a minimal ranks.ini and redirect all ConfigParser.read calls to it."""
    ranks_ini = tmp_path / "ranks.ini"
    ranks_ini.write_text(
        "[Group Ranking]\n"
        "0-99 = Bronze\n"
        "100-199 = Silver\n"
        "200+ = Gold\n"
    )
    original_read = configparser.ConfigParser.read

    def fake_read(self, filenames, encoding=None):
        return original_read(self, str(ranks_ini), encoding=encoding)

    monkeypatch.setattr(configparser.ConfigParser, "read", fake_read)
    return ranks_ini


@pytest.fixture
def player_ranks_json_file(tmp_path, sample_players):
    """Write sample player_ranks.json to tmp_path and return its path."""
    json_file = tmp_path / "player_ranks.json"
    json_file.write_text(json.dumps(sample_players))
    return json_file


@pytest.fixture
def sample_csv_file(tmp_path):
    """Write a CSV with multi-player EHB history and return its path."""
    csv_file = tmp_path / "ehb_log.csv"
    rows = [
        ["2025-01-01T10:00:00", "goblin_gaz", "3.0"],
        ["2025-02-01T10:00:00", "goblin_gaz", "5.0"],
        ["2025-01-15T10:00:00", "silver_sam", "120.0"],
        ["2025-03-01T10:00:00", "silver_sam", "150.0"],
        ["2025-06-01T10:00:00", "zenyte_zoe", "1600.0"],
    ]
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return csv_file
