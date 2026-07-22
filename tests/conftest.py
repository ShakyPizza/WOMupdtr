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

@pytest.fixture(autouse=True)
def isolate_database_path(monkeypatch, tmp_path):
    """Keep SQLite test writes inside a per-test temp directory."""
    monkeypatch.setenv("WOM_DATABASE_PATH", str(tmp_path / "database.db"))


@pytest.fixture
def sample_players():
    """Three players at different EHB / rank levels (with EHP fields)."""
    return {
        "goblin_gaz": {"last_ehb": 5.0, "rank": "Goblin", "last_ehp": 20.0, "ehp_rank": "Novice"},
        "silver_sam": {"last_ehb": 150.0, "rank": "Silver", "last_ehp": 400.0, "ehp_rank": "Adept"},
        "zenyte_zoe": {"last_ehb": 1600.0, "rank": "Zenyte", "last_ehp": 1800.0, "ehp_rank": "Master"},
    }


# ---------------------------------------------------------------------------
# Shared async WOM client stub (Feature foundation F2)
# ---------------------------------------------------------------------------


class FakeResult:
    """Minimal stand-in for wom.py's ``Result`` type."""

    def __init__(self, value=None, err=None):
        self._v = value
        self._e = err
        self.is_ok = err is None

    def unwrap(self):
        return self._v

    def unwrap_err(self):
        return self._e


def make_player(display_name, *, ehb=0.0, ehp=0.0, player_id=None, status="active",
                last_changed_at=None, updated_at=None):
    """Build a SimpleNamespace matching the fields WOM's Player exposes."""
    return types.SimpleNamespace(
        display_name=display_name,
        id=player_id if player_id is not None else abs(hash(display_name)) % 100000,
        ehb=ehb,
        ehp=ehp,
        status=status,
        last_changed_at=last_changed_at,
        updated_at=updated_at,
    )


def make_membership(player):
    """Build a group-membership namespace wrapping a player."""
    return types.SimpleNamespace(player=player)


def make_hiscores_entry(player, *, kills=0, rank=-1):
    """Build a GroupHiscoresEntry-shaped namespace (boss data)."""
    return types.SimpleNamespace(
        player=player,
        data=types.SimpleNamespace(kills=kills, rank=rank),
    )


def make_gains_entry(player, *, gained=0.0, start_date=None, end_date=None):
    """Build a GroupMemberGains-shaped namespace."""
    return types.SimpleNamespace(
        player=player,
        data=types.SimpleNamespace(gained=gained),
        start_date=start_date,
        end_date=end_date,
    )


class FakeGroupService:
    """Async group service returning canned FakeResult values."""

    def __init__(self, *, details=None, gains=None, hiscores=None):
        self._details = details
        self._gains = gains or {}
        self._hiscores = hiscores or {}
        self.calls = []

    async def get_details(self, group_id):
        self.calls.append(("get_details", group_id))
        if self._details is None:
            return FakeResult(err="no details configured")
        return FakeResult(value=self._details)

    async def get_gains(self, group_id, metric, *, period=None, start_date=None,
                        end_date=None, limit=None, offset=None):
        self.calls.append(("get_gains", metric, limit, offset))
        key = getattr(metric, "value", metric)
        entries = list(self._gains.get(key, []))
        page = entries[(offset or 0): (offset or 0) + (limit or len(entries))]
        return FakeResult(value=page)

    async def get_hiscores(self, group_id, metric, *, limit=None, offset=None):
        self.calls.append(("get_hiscores", metric, limit, offset))
        key = getattr(metric, "value", metric)
        entries = list(self._hiscores.get(key, []))
        page = entries[(offset or 0): (offset or 0) + (limit or len(entries))]
        return FakeResult(value=page)


class FakeWomClient:
    """Async WOM client stub exposing a ``groups`` service."""

    def __init__(self, *, details=None, gains=None, hiscores=None):
        self.groups = FakeGroupService(details=details, gains=gains, hiscores=hiscores)

    async def start(self):
        return None


@pytest.fixture
def fake_wom_client():
    """Factory fixture for a configurable async WOM client stub."""
    def _make(*, details=None, gains=None, hiscores=None):
        return FakeWomClient(details=details, gains=gains, hiscores=hiscores)
    return _make


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
        "\n"
        "[Skilling Ranking]\n"
        "0-100 = Novice\n"
        "100-500 = Apprentice\n"
        "500-1000 = Adept\n"
        "1000-1500 = Expert\n"
        "1500+ = Master\n"
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
        "\n"
        "[Skilling Ranking]\n"
        "0-99 = Wood\n"
        "100-199 = Stone\n"
        "200+ = Steel\n"
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
