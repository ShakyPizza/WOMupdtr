"""Tests for the outbound WOM API usage tracker / circuit breaker (utils.api_usage)."""

import asyncio

import pytest

from python.utils import api_usage
from python.utils import database


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# classify_endpoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url,expected", [
    ("https://api.wiseoldman.net/v2/groups/2300", "groups/{id}"),
    ("https://api.wiseoldman.net/v2/groups/2300/gains?metric=overall", "groups/{id}/gains"),
    ("https://api.wiseoldman.net/v2/groups/2300/update-all", "groups/{id}/update-all"),
    ("https://api.wiseoldman.net/v2/groups/2300/achievements", "groups/{id}/achievements"),
    ("https://api.wiseoldman.net/v2/groups/2300/name-changes", "groups/{id}/name-changes"),
    ("https://api.wiseoldman.net/v2/groups/2300/statistics", "groups/{id}/statistics"),
    ("https://api.wiseoldman.net/v2/groups/2300/hiscores", "groups/{id}/hiscores"),
    ("https://api.wiseoldman.net/v2/players/some_user", "players/{username}"),
    ("https://api.wiseoldman.net/v2/efficiency/rates", "other"),
])
def test_classify_endpoint(url, expected):
    assert api_usage.classify_endpoint(url) == expected


# ---------------------------------------------------------------------------
# ApiUsageTracker — circuit breaker behavior
# ---------------------------------------------------------------------------


def _make_tracker(monkeypatch, *, rate_limit=5, cooldown=60):
    now = {"t": 1000.0}
    monkeypatch.setattr(api_usage.time, "monotonic", lambda: now["t"])
    tracker = api_usage.ApiUsageTracker(
        rate_limit_per_minute=rate_limit, cooldown_seconds=cooldown, log=lambda msg: None,
    )
    return tracker, now


def test_tracker_allows_calls_under_limit(monkeypatch):
    tracker, _now = _make_tracker(monkeypatch, rate_limit=5)
    for _ in range(5):
        tracker.before_request("GET", "groups/{id}")
    assert tracker.breaker_status()["open"] is False


def test_tracker_trips_breaker_over_limit(monkeypatch):
    tracker, _now = _make_tracker(monkeypatch, rate_limit=5)
    for _ in range(5):
        tracker.before_request("GET", "groups/{id}")
    with pytest.raises(api_usage.ApiCircuitOpenError):
        tracker.before_request("GET", "groups/{id}")
    assert tracker.breaker_status()["open"] is True


def test_tracker_blocks_while_open_without_reopening_window(monkeypatch):
    """A tight retry loop against an open breaker must keep getting blocked cheaply."""
    tracker, _now = _make_tracker(monkeypatch, rate_limit=2)
    tracker.before_request("GET", "groups/{id}")
    tracker.before_request("GET", "groups/{id}")
    with pytest.raises(api_usage.ApiCircuitOpenError):
        tracker.before_request("GET", "groups/{id}")

    for _ in range(50):
        with pytest.raises(api_usage.ApiCircuitOpenError):
            tracker.before_request("GET", "groups/{id}")

    status = tracker.breaker_status()
    assert status["open"] is True
    assert status["blocked_since_open"] >= 50


def test_tracker_closes_after_cooldown(monkeypatch):
    tracker, now = _make_tracker(monkeypatch, rate_limit=1, cooldown=30)
    tracker.before_request("GET", "groups/{id}")
    with pytest.raises(api_usage.ApiCircuitOpenError):
        tracker.before_request("GET", "groups/{id}")
    assert tracker.breaker_status()["open"] is True

    now["t"] += 31  # advance past the cooldown window
    tracker.before_request("GET", "groups/{id}")  # should not raise
    assert tracker.breaker_status()["open"] is False


def test_tracker_rolling_window_drops_old_calls(monkeypatch):
    tracker, now = _make_tracker(monkeypatch, rate_limit=3)
    tracker.before_request("GET", "groups/{id}")
    tracker.before_request("GET", "groups/{id}")
    now["t"] += 61  # first two calls fall outside the 60s window
    tracker.before_request("GET", "groups/{id}")
    tracker.before_request("GET", "groups/{id}")
    tracker.before_request("GET", "groups/{id}")
    assert tracker.breaker_status()["open"] is False


# ---------------------------------------------------------------------------
# _tracking_middleware — end-to-end request wrapping
# ---------------------------------------------------------------------------


class _FakeRequest:
    def __init__(self, method, url):
        self.method = method
        self.url = url


class _FakeResponse:
    def __init__(self, status):
        self.status = status


def test_middleware_records_successful_call(monkeypatch):
    logged = []
    monkeypatch.setattr(
        api_usage, "tracker",
        api_usage.ApiUsageTracker(rate_limit_per_minute=30, cooldown_seconds=60, log=logged.append),
    )
    request = _FakeRequest("GET", "https://api.wiseoldman.net/v2/groups/2300")

    async def handler(_req):
        return _FakeResponse(200)

    response = run(api_usage._tracking_middleware(request, handler))
    assert response.status == 200

    recent = database.read_recent_api_calls(limit=1)
    assert recent[0]["endpoint"] == "groups/{id}"
    assert recent[0]["status_code"] == 200
    assert recent[0]["outcome"] == "ok"

    # Every real call is also surfaced to the console/log callback, not just SQLite.
    assert len(logged) == 1
    assert "GET groups/{id} -> 200" in logged[0]


def test_middleware_records_error_and_reraises(monkeypatch):
    monkeypatch.setattr(
        api_usage, "tracker",
        api_usage.ApiUsageTracker(rate_limit_per_minute=30, cooldown_seconds=60, log=lambda m: None),
    )
    request = _FakeRequest("GET", "https://api.wiseoldman.net/v2/groups/2300/gains")

    async def handler(_req):
        raise ConnectionError("boom")

    with pytest.raises(ConnectionError):
        run(api_usage._tracking_middleware(request, handler))

    recent = database.read_recent_api_calls(limit=1)
    assert recent[0]["endpoint"] == "groups/{id}/gains"
    assert recent[0]["outcome"] == "error"
    assert recent[0]["status_code"] is None


def test_middleware_blocks_when_breaker_open(monkeypatch):
    monkeypatch.setattr(
        api_usage, "tracker",
        api_usage.ApiUsageTracker(rate_limit_per_minute=1, cooldown_seconds=60, log=lambda m: None),
    )
    request = _FakeRequest("GET", "https://api.wiseoldman.net/v2/groups/2300")

    calls = []

    async def handler(_req):
        calls.append(1)
        return _FakeResponse(200)

    run(api_usage._tracking_middleware(request, handler))
    with pytest.raises(api_usage.ApiCircuitOpenError):
        run(api_usage._tracking_middleware(request, handler))

    assert calls == [1]  # the blocked call never reached the network


# ---------------------------------------------------------------------------
# create_tracked_session — wiring
# ---------------------------------------------------------------------------


def test_create_tracked_session_attaches_tracking_middleware():
    async def _noop_middleware(request, handler):
        return await handler(request)

    async def _check():
        session = api_usage.create_tracked_session(middlewares=[_noop_middleware])
        try:
            assert api_usage._tracking_middleware in session._middlewares
            assert _noop_middleware in session._middlewares
        finally:
            await session.close()

    run(_check())
