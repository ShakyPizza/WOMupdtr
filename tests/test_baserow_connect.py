"""Tests for python/utils/baserow_connect.py."""

import types
import pytest

from python.utils import baserow_connect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_response(status_code, json_data=None):
    """Build a minimal fake requests.Response-like object."""
    resp = types.SimpleNamespace()
    resp.status_code = status_code
    resp.json = lambda: (json_data if json_data is not None else {})
    return resp


# ---------------------------------------------------------------------------
# post_to_ehb_table
# ---------------------------------------------------------------------------

def test_post_to_ehb_table_calls_post_with_correct_payload(monkeypatch):
    """With a valid token, requests.post is called with username/date/ehb."""
    monkeypatch.setattr(baserow_connect, "token", "test-token")

    calls = []

    def fake_post(url, headers=None, json=None):
        calls.append({"url": url, "json": json})
        return _fake_response(200)

    monkeypatch.setattr(baserow_connect.requests, "post", fake_post)

    baserow_connect.post_to_ehb_table("alice", "2025-06-01", 150.0)

    assert len(calls) == 1
    assert calls[0]["json"]["Username"] == "alice"
    assert calls[0]["json"]["Date"] == "2025-06-01"
    assert calls[0]["json"]["EHB"] == 150.0


def test_post_to_ehb_table_no_op_when_token_empty(monkeypatch):
    """With no token configured the function returns without calling requests."""
    monkeypatch.setattr(baserow_connect, "token", "")

    calls = []
    monkeypatch.setattr(baserow_connect.requests, "post", lambda *a, **k: calls.append(True))

    baserow_connect.post_to_ehb_table("alice", "2025-06-01", 150.0)

    assert calls == []


# ---------------------------------------------------------------------------
# update_players_table — player does not exist (GET returns empty results)
# ---------------------------------------------------------------------------

def test_update_players_table_creates_new_player(monkeypatch):
    """When the GET lookup returns no results, POST is called to create the row."""
    monkeypatch.setattr(baserow_connect, "token", "test-token")

    post_calls = []
    patch_calls = []

    def fake_get(url, headers=None):
        return _fake_response(200, {"results": []})

    def fake_post(url, headers=None, json=None):
        post_calls.append(json)
        return _fake_response(200)

    def fake_patch(url, headers=None, json=None):
        patch_calls.append(json)
        return _fake_response(200)

    monkeypatch.setattr(baserow_connect.requests, "get", fake_get)
    monkeypatch.setattr(baserow_connect.requests, "post", fake_post)
    monkeypatch.setattr(baserow_connect.requests, "patch", fake_patch)

    baserow_connect.update_players_table("alice", "Silver", 150.0)

    assert len(post_calls) == 1
    assert post_calls[0]["Username"] == "alice"
    assert post_calls[0]["Rank"] == "Silver"
    assert patch_calls == []


# ---------------------------------------------------------------------------
# update_players_table — player already exists (GET returns a result)
# ---------------------------------------------------------------------------

def test_update_players_table_patches_existing_player(monkeypatch):
    """When the GET lookup finds an existing row, PATCH is called instead of POST."""
    monkeypatch.setattr(baserow_connect, "token", "test-token")

    post_calls = []
    patch_calls = []

    def fake_get(url, headers=None):
        return _fake_response(200, {"results": [{"id": 99}]})

    def fake_post(url, headers=None, json=None):
        post_calls.append(json)
        return _fake_response(200)

    def fake_patch(url, headers=None, json=None):
        patch_calls.append({"url": url, "json": json})
        return _fake_response(200)

    monkeypatch.setattr(baserow_connect.requests, "get", fake_get)
    monkeypatch.setattr(baserow_connect.requests, "post", fake_post)
    monkeypatch.setattr(baserow_connect.requests, "patch", fake_patch)

    baserow_connect.update_players_table("alice", "Silver", 150.0)

    assert len(patch_calls) == 1
    assert patch_calls[0]["json"]["Username"] == "alice"
    assert "99" in patch_calls[0]["url"]
    assert post_calls == []


def test_update_players_table_no_op_when_token_empty(monkeypatch):
    """No HTTP calls are made when token is empty."""
    monkeypatch.setattr(baserow_connect, "token", "")

    calls = []
    monkeypatch.setattr(baserow_connect.requests, "get", lambda *a, **k: calls.append("get"))
    monkeypatch.setattr(baserow_connect.requests, "post", lambda *a, **k: calls.append("post"))
    monkeypatch.setattr(baserow_connect.requests, "patch", lambda *a, **k: calls.append("patch"))

    baserow_connect.update_players_table("alice", "Silver", 150.0)

    assert calls == []


def test_update_players_table_payload_omits_removed_fan_field(monkeypatch):
    """The Baserow payload no longer includes the removed fan field."""
    monkeypatch.setattr(baserow_connect, "token", "test-token")

    post_calls = []

    monkeypatch.setattr(baserow_connect.requests, "get",
                        lambda *a, **k: _fake_response(200, {"results": []}))
    monkeypatch.setattr(baserow_connect.requests, "post",
                        lambda url, headers=None, json=None: post_calls.append(json) or _fake_response(200))
    monkeypatch.setattr(baserow_connect.requests, "patch", lambda *a, **k: _fake_response(200))

    baserow_connect.update_players_table("carol", "Gold", 300.0)

    assert "discord_name" not in post_calls[0]


# ---------------------------------------------------------------------------
# update_players_table — non-200 GET response
# ---------------------------------------------------------------------------

def test_update_players_table_handles_failed_get_gracefully(monkeypatch):
    """A non-200 GET response does not raise an exception."""
    monkeypatch.setattr(baserow_connect, "token", "test-token")

    monkeypatch.setattr(baserow_connect.requests, "get",
                        lambda *a, **k: _fake_response(500))
    monkeypatch.setattr(baserow_connect.requests, "post",
                        lambda *a, **k: _fake_response(200))
    monkeypatch.setattr(baserow_connect.requests, "patch",
                        lambda *a, **k: _fake_response(200))

    # Should not raise
    baserow_connect.update_players_table("dave", "Bronze", 5.0)
