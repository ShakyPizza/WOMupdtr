# Data retention roadmap

This roadmap describes how WOMupdtr can retain more useful Wise Old Man (WOM)
data while keeping collection bounded, normalized, and maintainable. It favors
data already returned by existing scheduled calls before introducing additional
API traffic.

## Phase 1: achievement retention (completed)

Phase 1 adds normalized storage for:

- stable WOM player identities;
- observed player-name aliases; and
- achievement events, deduplicated by WOM player ID, metric, measure, and
  threshold.

Weekly, monthly, and yearly report fetches now persist achievements already
present in their WOM responses. Reports surface relevant boss kill-count, XP,
and level milestones when available. Existing report behavior is unchanged when
no matching events are returned.

The implementation deliberately does not store raw API payloads, make extra WOM
requests, backfill historical periods, or replace username-based legacy history.
Report generation remains available if achievement persistence fails.

## Phase 2: membership and freshness

Retain group membership observations from successful group-detail refreshes,
including stable player ID, role, joined/left state where observable, and first
and last seen timestamps. Record a freshness timestamp for every retained data
family so the dashboard can distinguish current, stale, and unavailable data.

Only complete successful responses should advance freshness or close a
membership interval. Partial API failures must not make members appear to have
left. Avoid retaining moderation, patron, or other account metadata unless a
specific product feature requires it.

## Phase 3: optional achievement backfill

Add an operator-controlled, resumable backfill for a bounded date range. Reuse
the Phase 1 normalization and deduplication rules, checkpoint completed windows,
respect WOM rate limits, and make retries idempotent. Backfill should be disabled
by default and must never delete current data because an older window is missing
or incomplete.

## Phase 4: gains and stat snapshots

Associate gains rows with stable player IDs and explicit observation windows.
Then retain selected player or group stat snapshots already returned by scheduled
collection, prioritizing metrics used by reports and charts. Prefer normalized
numeric observations and derived aggregates over raw payloads.

Before increasing snapshot frequency or metric coverage, define retention and
downsampling rules for overlapping windows. Long-term summaries can retain daily
or weekly aggregates while expiring redundant high-frequency observations.

## Phase 5: legacy identity migration

Measure how reliably legacy username-keyed EHB, EHP, boss, and gains history can
be mapped to stable WOM player IDs. Automatically migrate only unambiguous
matches, preserve unmatched rows, and use alias history to support verified name
changes. Schema changes should be versioned and reversible, with explicit
handling for deleted or anonymized players.

## Ongoing boundaries

- Store fields that support a defined report, chart, audit, or operational need.
- Prefer stable identifiers and typed columns over usernames and JSON blobs.
- Treat API timestamps and collection timestamps as separate facts.
- Keep ingestion idempotent and tolerant of missing optional WOM fields.
- Document retention periods before collecting materially higher-volume data.
