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

# Every WOM route this bot's code actually calls today, for reference (see
# wom.py's own routes.py for the full, authoritative catalog — that library
# module is what classify_endpoint below is deliberately kept in sync with,
# without hard-depending on its internals):
#   GET  /groups/{id}                  groups.get_details
#   GET  /groups/{id}/gained           groups.get_gains        (note: "gained", not "gains")
#   POST /groups/{id}/update-all       groups.update_outdated_members / raw refresh_group_data
#   GET  /groups/{id}/achievements     groups.get_achievements
#   GET  /groups/{id}/name-changes     groups.get_name_changes
#   GET  /groups/{id}/statistics       groups.get_statistics
#
# A previous version of this function matched "/gains" instead of the real
# "/gained" path segment above, so every gains call silently fell into the
# generic "other" bucket. To make that class of bug impossible to repeat,
# classification is now a generic path normalizer rather than a hand-written
# per-endpoint whitelist: any WOM endpoint, including ones added later, gets
# a stable, readable label automatically instead of disappearing into "other".


def classify_endpoint(url: str) -> str:
    """Collapse a WOM API URL into a readable label for the audit log.

    Strips the scheme/host and API version prefix, keeping the real path
    (including the actual group/player/competition ID) so the admin view
    shows exactly what was requested. Falls back to ``"other"`` only for a
    URL with no path segments at all.
    """
    path = url.split("?", 1)[0]
    path = re.sub(r"^https?://[^/]+", "", path)
    path = re.sub(r"^/v\d+", "", path)
    segments = [seg for seg in path.split("/") if seg]
    if not segments:
        return "other"
    return "/".join(segments)


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
        user_agent: Optional[str] = None,
    ) -> None:
        if outcome == "ok":
            self._log(f"WOM API {method} {endpoint} -> {status_code} ({duration_ms}ms)")
        else:
            self._log(f"WOM API {method} {endpoint} -> {outcome} ({duration_ms}ms)")
        log_api_call(
            method=method, endpoint=endpoint,
            status_code=status_code, duration_ms=duration_ms, outcome=outcome,
            user_agent=user_agent,
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
    user_agent = request.headers.get("User-Agent")
    tracker.before_request(method, endpoint)

    start = time.monotonic()
    try:
        response = await handler(request)
    except Exception:
        duration_ms = int((time.monotonic() - start) * 1000)
        tracker.record_completed(
            method=method, endpoint=endpoint, user_agent=user_agent,
            status_code=None, duration_ms=duration_ms, outcome="error",
        )
        raise

    duration_ms = int((time.monotonic() - start) * 1000)
    tracker.record_completed(
        method=method, endpoint=endpoint, user_agent=user_agent,
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
