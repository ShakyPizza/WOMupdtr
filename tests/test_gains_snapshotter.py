"""Tests for the persisted gains snapshotter — Feature 4."""

import asyncio
from datetime import datetime, timezone
import types

import pytest

from python.gainstracker import gains_snapshotter
from python.utils import database
from tests.conftest import make_gains_entry, make_player


NOW = datetime(2025, 1, 8, 0, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_resolve_metric_known():
    assert gains_snapshotter.resolve_metric("overall") is not None
    assert gains_snapshotter.resolve_metric("ehb") is not None
    assert gains_snapshotter.resolve_metric("EHB") is not None


def test_resolve_metric_unknown():
    assert gains_snapshotter.resolve_metric("not_a_metric") is None
    assert gains_snapshotter.resolve_metric("") is None


def test_build_gains_rows_skips_nameless_entries():
    entries = [
        make_gains_entry(make_player("alice"), gained=1000.0),
        make_gains_entry(make_player(""), gained=5.0),  # dropped
    ]
    rows = gains_snapshotter._build_gains_rows(
        entries,
        snapshot_time="2025-01-08 00:00:00",
        period_start="2025-01-01 00:00:00",
        period_end="2025-01-08 00:00:00",
        metric="overall",
    )
    assert len(rows) == 1
    assert rows[0]["username"] == "alice"
    assert rows[0]["gained"] == 1000.0
    assert rows[0]["metric"] == "overall"


def test_build_gains_lines_formats_leaderboard():
    lines = gains_snapshotter.build_gains_lines("overall", 7, [("alice", 5000.0), ("bob", 3000.0)])
    joined = "\n".join(lines)
    assert "alice" in joined
    assert "last 7d" in joined


def test_build_gains_lines_empty():
    lines = gains_snapshotter.build_gains_lines("ehb", 7, [])
    assert any("No gains data" in line for line in lines)


# ---------------------------------------------------------------------------
# snapshot_gains_once — DB integration
# ---------------------------------------------------------------------------

def _log(_msg):
    pass


def test_snapshot_gains_once_persists(fake_wom_client, tmp_path):
    client = fake_wom_client(gains={
        "overall": [
            make_gains_entry(make_player("alice"), gained=5000.0),
            make_gains_entry(make_player("bob"), gained=3000.0),
        ],
    })

    inserted = run(gains_snapshotter.snapshot_gains_once(
        wom_client=client,
        group_id=1,
        metrics=["overall"],
        window_days=7,
        log=_log,
        now=NOW,
    ))

    assert inserted == 2
    rows = database.read_latest_gains("overall")
    assert {r["username"] for r in rows} == {"alice", "bob"}
    # period math: snapshot at NOW, start 7 days earlier
    assert rows[0]["period_end"] == "2025-01-08 00:00:00"
    assert rows[0]["period_start"] == "2025-01-01 00:00:00"


def test_snapshot_gains_once_idempotent(fake_wom_client, tmp_path):
    client = fake_wom_client(gains={
        "overall": [make_gains_entry(make_player("alice"), gained=5000.0)],
    })
    kwargs = dict(wom_client=client, group_id=1, metrics=["overall"], window_days=7, log=_log, now=NOW)

    first = run(gains_snapshotter.snapshot_gains_once(**kwargs))
    second = run(gains_snapshotter.snapshot_gains_once(**kwargs))

    assert first == 1
    assert second == 0  # same snapshot_time+user+metric → INSERT OR IGNORE


def test_snapshot_gains_once_multi_metric(fake_wom_client, tmp_path):
    client = fake_wom_client(gains={
        "overall": [make_gains_entry(make_player("alice"), gained=5000.0)],
        "ehb": [make_gains_entry(make_player("alice"), gained=2.0)],
    })
    inserted = run(gains_snapshotter.snapshot_gains_once(
        wom_client=client, group_id=1, metrics=["overall", "ehb"], window_days=7, log=_log, now=NOW,
    ))
    assert inserted == 2
    assert database.read_latest_gains("ehb")
    assert database.read_latest_gains("overall")


def test_snapshot_gains_once_accepts_full_response_beyond_50(fake_wom_client):
    entries = [make_gains_entry(make_player(f"p{i}"), gained=float(i)) for i in range(120)]
    client = fake_wom_client(gains={"overall": entries})

    inserted = run(gains_snapshotter.snapshot_gains_once(
        wom_client=client, group_id=1, metrics=["overall"], window_days=7, log=_log, now=NOW,
    ))
    assert inserted == 120
    assert client.groups.calls == [
        ("get_gains", gains_snapshotter.resolve_metric("overall"), None, None)
    ]


def test_collect_gains_leaderboard_sorted(fake_wom_client):
    client = fake_wom_client(gains={
        "overall": [
            make_gains_entry(make_player("low"), gained=10.0),
            make_gains_entry(make_player("high"), gained=999.0),
        ],
    })
    board = run(gains_snapshotter.collect_gains_leaderboard(
        wom_client=client, group_id=1, metric_name="overall", window_days=7, log=_log, now=NOW,
    ))
    assert board[0] == ("high", 999.0)
    assert board[1] == ("low", 10.0)


# ---------------------------------------------------------------------------
# API failure handling and snapshot atomicity
# ---------------------------------------------------------------------------

def test_snapshot_gains_first_page_failure_writes_nothing(fake_wom_client):
    client = fake_wom_client(gains_errors={("overall", 0): "WOM unavailable"})

    with pytest.raises(RuntimeError, match="overall.*WOM unavailable"):
        run(gains_snapshotter.snapshot_gains_once(
            wom_client=client,
            group_id=1,
            metrics=["overall"],
            window_days=7,
            log=_log,
            now=NOW,
        ))

    assert database.read_latest_gains("overall") == []


def test_snapshot_gains_does_not_request_later_pages(fake_wom_client):
    entries = [make_gains_entry(make_player(f"p{i}"), gained=float(i)) for i in range(75)]
    client = fake_wom_client(
        gains={"overall": entries},
        gains_errors={("overall", 50): "page failed"},
    )

    inserted = run(gains_snapshotter.snapshot_gains_once(
        wom_client=client,
        group_id=1,
        metrics=["overall"],
        window_days=7,
        log=_log,
        now=NOW,
    ))

    assert inserted == 75
    assert len(database.read_latest_gains("overall", limit=100)) == 75
    assert len(client.groups.calls) == 1


def test_snapshot_gains_multi_metric_failure_is_atomic(fake_wom_client):
    client = fake_wom_client(
        gains={"overall": [make_gains_entry(make_player("alice"), gained=5000.0)]},
        gains_errors={("ehb", 0): "EHB failed"},
    )

    with pytest.raises(RuntimeError, match="ehb.*EHB failed"):
        run(gains_snapshotter.snapshot_gains_once(
            wom_client=client,
            group_id=1,
            metrics=["overall", "ehb"],
            window_days=7,
            log=_log,
            now=NOW,
        ))

    assert database.read_latest_gains("overall") == []
    assert database.read_latest_gains("ehb") == []


def test_snapshot_gains_requires_at_least_one_valid_metric(fake_wom_client):
    client = fake_wom_client()

    with pytest.raises(ValueError, match="no valid metrics"):
        run(gains_snapshotter.snapshot_gains_once(
            wom_client=client,
            group_id=1,
            metrics=["not_a_metric"],
            window_days=7,
            log=_log,
            now=NOW,
        ))


def test_live_gains_leaderboard_propagates_api_failure(fake_wom_client):
    client = fake_wom_client(gains_errors={("overall", 0): "live failed"})

    with pytest.raises(RuntimeError, match="overall.*live failed"):
        run(gains_snapshotter.collect_gains_leaderboard(
            wom_client=client,
            group_id=1,
            metric_name="overall",
            window_days=7,
            log=_log,
            now=NOW,
        ))


def test_snapshot_loop_does_not_publish_or_mark_failed_cycle(fake_wom_client, monkeypatch):
    client = fake_wom_client(gains_errors={("overall", 0): "scheduled failure"})
    snapshot_calls = []
    channel_lookups = []
    logs = []

    async def stop_after_first_cycle(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(gains_snapshotter.asyncio, "sleep", stop_after_first_cycle)
    discord_client = types.SimpleNamespace(
        get_channel=lambda channel_id: channel_lookups.append(channel_id)
    )

    with pytest.raises(asyncio.CancelledError):
        run(gains_snapshotter._gains_snapshot_loop(
            wom_client=client,
            discord_client=discord_client,
            group_id=1,
            channel_id=123,
            metrics=["overall"],
            window_days=7,
            interval_seconds=60,
            log=logs.append,
            on_snapshot=lambda: snapshot_calls.append(True),
        ))

    assert snapshot_calls == []
    assert channel_lookups == []
    assert any("scheduled failure" in message for message in logs)
