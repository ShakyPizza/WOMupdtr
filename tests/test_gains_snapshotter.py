"""Tests for the persisted gains snapshotter — Feature 4."""

import asyncio
from datetime import datetime, timezone

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


def test_snapshot_gains_once_paginates_beyond_50(fake_wom_client):
    entries = [make_gains_entry(make_player(f"p{i}"), gained=float(i)) for i in range(120)]
    client = fake_wom_client(gains={"overall": entries})

    inserted = run(gains_snapshotter.snapshot_gains_once(
        wom_client=client, group_id=1, metrics=["overall"], window_days=7, log=_log, now=NOW,
    ))
    assert inserted == 120


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
