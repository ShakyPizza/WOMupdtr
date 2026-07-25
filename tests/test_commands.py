"""Focused tests for Discord command output helpers."""

from python.utils.commands import _format_lookup_message


def test_format_lookup_message_includes_total_xp_and_preserves_ehp():
    message = _format_lookup_message(
        "Alice",
        {
            "last_ehb": 42.5,
            "rank": "Silver",
            "last_ehp": 300.25,
            "ehp_rank": "Adept",
            "total_xp": 123456789,
        },
    )

    assert "**Rank:** Silver (42.5 EHB)" in message
    assert "**Skilling Rank:** Adept (300.25 EHP)" in message
    assert "**Total XP:** 123,456,789" in message


def test_format_lookup_message_explains_missing_total_xp_for_legacy_row():
    message = _format_lookup_message(
        "Legacy",
        {"last_ehb": 5, "rank": "Goblin"},
    )

    assert "**Total XP:** Not available yet (run a rank refresh)" in message
