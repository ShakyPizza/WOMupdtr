"""Integration tests for FastAPI JSON API endpoints."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.services.bot_state import BotState
from web.routers import admin, charts, group, players


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bot_state(**kwargs) -> BotState:
    defaults = dict(
        check_interval=3600,
        post_to_discord=True,
        silent=False,
        debug=False,
        bot_started_at=datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
        last_rank_check=datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
        last_group_refresh=datetime(2025, 6, 1, 11, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return BotState(**defaults)


def _make_app(bot_state: BotState) -> FastAPI:
    """Minimal FastAPI app with only the routers under test (no static mount)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.bot_state = bot_state
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(admin.router, prefix="/admin")
    app.include_router(charts.router, prefix="/charts")
    app.include_router(group.router, prefix="/group")
    app.include_router(players.router, prefix="/players")
    return app


# ---------------------------------------------------------------------------
# GET /admin/status
# ---------------------------------------------------------------------------

def test_admin_status_returns_200(monkeypatch):
    """Status endpoint returns HTTP 200."""
    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        response = client.get("/admin/status")
    assert response.status_code == 200


def test_admin_status_contains_expected_keys(monkeypatch):
    """Status JSON contains all expected top-level keys."""
    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        data = client.get("/admin/status").json()

    expected_keys = {
        "bot_started_at", "last_rank_check", "last_group_refresh",
        "check_interval", "silent", "debug", "post_to_discord",
    }
    assert expected_keys.issubset(data.keys())


def test_admin_status_reflects_state_values():
    """Status values match the injected BotState."""
    state = _make_bot_state(silent=True, debug=False, check_interval=7200)
    with TestClient(_make_app(state)) as client:
        data = client.get("/admin/status").json()

    assert data["silent"] is True
    assert data["debug"] is False
    assert data["check_interval"] == 7200


def test_admin_status_none_timestamps_when_not_set():
    """Timestamps that are None in BotState are serialised as null."""
    state = _make_bot_state(last_rank_check=None, last_group_refresh=None, bot_started_at=None)
    with TestClient(_make_app(state)) as client:
        data = client.get("/admin/status").json()

    assert data["last_rank_check"] is None
    assert data["last_group_refresh"] is None


# ---------------------------------------------------------------------------
# POST /admin/config
# ---------------------------------------------------------------------------

def test_admin_config_sets_silent_flag():
    """Posting silent=on flips BotState.silent to True."""
    state = _make_bot_state(silent=False, debug=False)
    with TestClient(_make_app(state)) as client:
        response = client.post("/admin/config", data={"silent": "on"})

    assert response.status_code == 200
    assert state.silent is True
    assert state.debug is False


def test_admin_config_clears_flags_when_absent():
    """Omitting a flag from the form sets it to False."""
    state = _make_bot_state(silent=True, debug=True)
    with TestClient(_make_app(state)) as client:
        client.post("/admin/config", data={})

    assert state.silent is False
    assert state.debug is False


def test_admin_config_sets_both_flags():
    """Both silent and debug can be set simultaneously."""
    state = _make_bot_state(silent=False, debug=False)
    with TestClient(_make_app(state)) as client:
        client.post("/admin/config", data={"silent": "on", "debug": "on"})

    assert state.silent is True
    assert state.debug is True


# ---------------------------------------------------------------------------
# GET /charts/api/rank-distribution
# ---------------------------------------------------------------------------

def test_rank_distribution_returns_200(monkeypatch, sample_players):
    """Rank distribution endpoint returns HTTP 200."""
    from web.services import ranks_service
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        response = client.get("/charts/api/rank-distribution")

    assert response.status_code == 200


def test_rank_distribution_returns_dict(monkeypatch, sample_players):
    """Rank distribution response is a JSON object (rank → count)."""
    from web.services import ranks_service
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        data = client.get("/charts/api/rank-distribution").json()

    assert isinstance(data, dict)
    assert data == {"Goblin": 1, "Silver": 1, "Zenyte": 1}


def test_rank_distribution_empty_when_no_players(monkeypatch):
    """Empty player set returns an empty dict."""
    from web.services import ranks_service
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: {})

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        data = client.get("/charts/api/rank-distribution").json()

    assert data == {}


# ---------------------------------------------------------------------------
# GET /charts/api/top-players
# ---------------------------------------------------------------------------

def test_top_players_returns_200(monkeypatch, sample_players):
    """Top-players endpoint returns HTTP 200."""
    from web.services import ranks_service
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        response = client.get("/charts/api/top-players")

    assert response.status_code == 200


def test_top_players_default_limit(monkeypatch, sample_players):
    """Without explicit limit, all 3 sample players are returned (< default 15)."""
    from web.services import ranks_service
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        data = client.get("/charts/api/top-players").json()

    assert isinstance(data, list)
    assert len(data) == 3


def test_top_players_respects_limit(monkeypatch, sample_players):
    """limit query parameter caps the number of players returned."""
    from web.services import ranks_service
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        data = client.get("/charts/api/top-players?limit=2").json()

    assert len(data) == 2
    # First entry should be the highest EHB player
    assert data[0]["username"] == "zenyte_zoe"


# ---------------------------------------------------------------------------
# GET /group/api/stats
# ---------------------------------------------------------------------------

def test_group_stats_returns_200(monkeypatch, sample_players):
    """Group stats endpoint returns HTTP 200."""
    from web.services import ranks_service
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        response = client.get("/group/api/stats")

    assert response.status_code == 200


def test_group_stats_contains_expected_keys(monkeypatch, sample_players):
    """Group stats JSON has total_players, total_ehb, avg_ehb, rank_distribution."""
    from web.services import ranks_service
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        data = client.get("/group/api/stats").json()

    assert set(data.keys()) >= {"total_players", "total_ehb", "avg_ehb", "rank_distribution"}


def test_group_stats_correct_totals(monkeypatch, sample_players):
    """Computed totals match the sample player data."""
    from web.services import ranks_service
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: sample_players)

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        data = client.get("/group/api/stats").json()

    assert data["total_players"] == 3
    # 5.0 + 150.0 + 1600.0 = 1755.0
    assert data["total_ehb"] == pytest.approx(1755.0, rel=1e-3)
    assert data["avg_ehb"] == pytest.approx(585.0, rel=1e-3)


def test_group_stats_zero_avg_when_no_players(monkeypatch):
    """No players produces zero averages without a division error."""
    from web.services import ranks_service
    monkeypatch.setattr(ranks_service, "load_ranks", lambda: {})

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        data = client.get("/group/api/stats").json()

    assert data["total_players"] == 0
    assert data["avg_ehb"] == 0


# ---------------------------------------------------------------------------
# GET /players/{username}/history
# ---------------------------------------------------------------------------

def test_player_history_returns_json_list(monkeypatch, sample_csv_file):
    """Player history endpoint returns a JSON array."""
    from web.services import csv_service
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(sample_csv_file))

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        response = client.get("/players/goblin_gaz/history")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2


def test_player_history_empty_for_unknown_player(monkeypatch, sample_csv_file):
    """Unknown player returns an empty JSON array (not 404)."""
    from web.services import csv_service
    monkeypatch.setattr(csv_service, "_resolve_csv_path", lambda _: str(sample_csv_file))

    state = _make_bot_state()
    with TestClient(_make_app(state)) as client:
        response = client.get("/players/no_such_player/history")

    assert response.status_code == 200
    assert response.json() == []
