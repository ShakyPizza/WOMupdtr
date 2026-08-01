"""Central tracking and circuit breaker for every outbound Wise Old Man API call.

Added after the 2026-07-23/07-25 IP-block incident (see the incident report):
an unbounded pagination loop in ``weeklyupdater/weekly_reporter.py`` produced
thousands of requests with no visibility until the WOM admin blocked the
server's IP. That specific bug is fixed, but nothing caught it while it was
happening. This module is the safety net for the next one:

- Every outbound call is classified, timed, and persisted to SQLite
  (``utils.database.log_api_call``) so usage is auditable after the fact.
- A rolling per-minute rate counter trips a circuit breaker that blocks
  further outbound calls for a cooldown period, so a future runaway loop
  gets stopped automatically instead of running until someone notices.

Every ``aiohttp.ClientSession`` that talks to the WOM API — the wom.py
client's internal session and any raw diagnostic/admin session — must be
constructed via :func:`create_tracked_session` so nothing can bypass this.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from collections import deque
from typing import Callable, Optional

import aiohttp

from .database import log_api_call

# Collapse WOM API URLs into a small set of stable labels for aggregation.
# Order matters: more specific patterns must come before their prefixes.
_ENDPOINT_PATTERNS = [
    (re.compile(r"/groups/\d+/update-all"), "groups/{id}/update-all"),
    (re.compile(r"/groups/\d+/gains"), "groups/{id}/gains"),
    (re.compile(r"/groups/\d+/achievements"), "groups/{id}/achievements"),
    (re.compile(r"/groups/\d+/name-changes"), "groups/{id}/name-changes"),
    (re.compile(r"/groups/\d+/statistics"), "groups/{id}/statistics"),
    (re.compile(r"/groups/\d+/hiscores"), "groups/{id}/hiscores"),
    (re.compile(r"/groups/\d+$"), "groups/{id}"),
    (re.compile(r"/players/[^/]+"), "players/{username}"),
]


def classify_endpoint(url: str) -> str:
    """Collapse a WOM API URL into a low-cardinality label for aggregation."""
    path = url.split("?", 1)[0]
    for pattern, label in _ENDPOINT_PATTERNS:
        if pattern.search(path):
            return label
    return "other"


class ApiCircuitOpenError(RuntimeError):
    """Raised in place of making a request while the circuit breaker is open."""


@dataclass
class _BreakerState:
    open_until: Optional[float] = None
    blocked_since_open: int = 0


class ApiUsageTracker:
    """Rolling-window rate tracker and circuit breaker shared by every session."""

    def __init__(
        self,
        *,
        rate_limit_per_minute: int = 30,
        cooldown_seconds: int = 300,
        log: Callable[[str], None] = print,
    ) -> None:
        self.rate_limit_per_minute = rate_limit_per_minute
        self.cooldown_seconds = cooldown_seconds
        self._log = log
        self._recent: deque = deque()
        self._breaker = _BreakerState()

    def configure(
        self,
        *,
        rate_limit_per_minute: int,
        cooldown_seconds: int,
        log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.rate_limit_per_minute = rate_limit_per_minute
        self.cooldown_seconds = cooldown_seconds
        if log is not None:
            self._log = log

    def before_request(self, method: str, endpoint: str) -> None:
        """Raise :class:`ApiCircuitOpenError` if this call should be blocked.

        Must be called synchronously, before any network I/O happens, so a
        tight retry loop that ignores the exception can't still slip real
        requests out between checks.
        """
        now = time.monotonic()

        if self._breaker.open_until is not None:
            if now < self._breaker.open_until:
                self._breaker.blocked_since_open += 1
                raise ApiCircuitOpenError(
                    f"WOM API circuit breaker is open ({self._breaker.blocked_since_open} "
                    f"call(s) blocked so far this trip); refusing {method} {endpoint}."
                )
            blocked = self._breaker.blocked_since_open
            self._breaker = _BreakerState()
            self._log(
                f"WOM API circuit breaker closed after cooldown "
                f"({blocked} call(s) were blocked while open)."
            )
            log_api_call(
                method=method, endpoint=endpoint,
                status_code=None, duration_ms=None, outcome="circuit_closed",
            )

        self._recent.append(now)
        window_start = now - 60
        while self._recent and self._recent[0] < window_start:
            self._recent.popleft()

        if len(self._recent) > self.rate_limit_per_minute:
            self._breaker = _BreakerState(open_until=now + self.cooldown_seconds, blocked_since_open=1)
            self._recent.clear()
            self._log(
                f"WOM API circuit breaker OPEN: more than {self.rate_limit_per_minute} "
                f"requests/min, triggered by {method} {endpoint}. Pausing all WOM API "
                f"calls for {self.cooldown_seconds}s."
            )
            log_api_call(
                method=method, endpoint=endpoint,
                status_code=None, duration_ms=None, outcome="circuit_opened",
            )
            raise ApiCircuitOpenError(
                f"WOM API circuit breaker just tripped on {method} {endpoint}; "
                f"pausing for {self.cooldown_seconds}s."
            )

    def record_completed(
        self,
        *,
        method: str,
        endpoint: str,
        status_code: Optional[int],
        duration_ms: int,
        outcome: str,
    ) -> None:
        if outcome == "ok":
            self._log(f"WOM API {method} {endpoint} -> {status_code} ({duration_ms}ms)")
        else:
            self._log(f"WOM API {method} {endpoint} -> {outcome} ({duration_ms}ms)")
        log_api_call(
            method=method, endpoint=endpoint,
            status_code=status_code, duration_ms=duration_ms, outcome=outcome,
        )

    def calls_in_last(self, seconds: int) -> int:
        """Count real (non-blocked) calls within the trailing window, in-memory."""
        cutoff = time.monotonic() - seconds
        return sum(1 for t in self._recent if t >= cutoff)

    def breaker_status(self) -> dict:
        now = time.monotonic()
        is_open = self._breaker.open_until is not None and now < self._breaker.open_until
        return {
            "open": is_open,
            "seconds_remaining": max(0, int(self._breaker.open_until - now)) if is_open else 0,
            "blocked_since_open": self._breaker.blocked_since_open if is_open else 0,
        }


# Single shared tracker for the whole process — every tracked session reports
# into it, so the breaker sees total request volume across all call sites.
tracker = ApiUsageTracker()


async def _tracking_middleware(request, handler):
    """aiohttp client middleware: gate + time + log every request through ``tracker``."""
    endpoint = classify_endpoint(str(request.url))
    method = request.method
    tracker.before_request(method, endpoint)

    start = time.monotonic()
    try:
        response = await handler(request)
    except Exception:
        duration_ms = int((time.monotonic() - start) * 1000)
        tracker.record_completed(
            method=method, endpoint=endpoint,
            status_code=None, duration_ms=duration_ms, outcome="error",
        )
        raise

    duration_ms = int((time.monotonic() - start) * 1000)
    tracker.record_completed(
        method=method, endpoint=endpoint,
        status_code=response.status, duration_ms=duration_ms, outcome="ok",
    )
    return response


def create_tracked_session(**kwargs) -> aiohttp.ClientSession:
    """Build an ``aiohttp.ClientSession`` that reports every request to ``tracker``.

    Use this instead of ``aiohttp.ClientSession(...)`` for every session that
    talks to the WOM API, so no outbound call — scheduled task, slash command,
    or one-off diagnostic — can bypass the shared rate tracking and circuit
    breaker.
    """
    middlewares = list(kwargs.pop("middlewares", ()))
    middlewares.append(_tracking_middleware)
    return aiohttp.ClientSession(middlewares=middlewares, **kwargs)
