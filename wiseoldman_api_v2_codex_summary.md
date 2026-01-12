# Wise Old Man (WOM) REST API v2 — Codex-friendly summary (partial)

This file is a **best-effort extract** from the public docs site, intended to be easy for code-generation / LLM tools to ingest.
It is **NOT** an official OpenAPI spec, and may be incomplete.

Sources (human reference):
- https://docs.wiseoldman.net/api
- https://docs.wiseoldman.net/api/global-type-definitions
- https://docs.wiseoldman.net/api/players/player-type-definitions
- https://docs.wiseoldman.net/api/players/player-endpoints
- https://docs.wiseoldman.net/api/groups/group-type-definitions
- https://docs.wiseoldman.net/api/groups/group-endpoints
- https://docs.wiseoldman.net/api/competitions/competition-type-definitions
- https://docs.wiseoldman.net/api/competitions/competition-endpoints
- https://docs.wiseoldman.net/api/records/record-endpoints
- https://docs.wiseoldman.net/api/deltas/delta-endpoints
- https://docs.wiseoldman.net/api/name-changes/name-endpoints
- https://docs.wiseoldman.net/api/efficiency/efficiency-endpoints

---

## Basics

base_url: https://api.wiseoldman.net/v2

rate_limits:
  unauthenticated:
    max_requests: 20
    per_seconds: 60
  api_key:
    max_requests: 100
    per_seconds: 60
  notes:
    - Add delays between requests to reduce load; excessive auto-updating can result in bans.
    - You can provide `x-api-key` and a User-Agent header.

headers:
  optional:
    - name: x-api-key
      description: API key issued by WOM (increases rate limit).
    - name: User-Agent
      description: A contactable identifier (often your Discord name).

pagination:
  query_params: [limit, offset]
  defaults:
    limit: 20
    offset: 0
  max_limit: 50
  exceptions:
    - /groups/:id/hiscores
    - /groups/:id/gained
    - some endpoints may not enforce max limit

date_format: ISO8601 date-time strings

status_codes:
  success: [200, 201]
  errors: [400, 403, 404, 429, 500]

---

## Global enums (partial lists)

enums:
  period:
    - five_min
    - day
    - week
    - month
    - year
  computed_metric:
    - ehp
    - ehb
  # Metric is a union of Skill + Activity + Boss + ComputedMetric.
  # The docs include long lists (skills/activities/bosses); see sources above.

---

## Endpoints (partial)

endpoints:

  # -----------------------------
  # Players
  # -----------------------------
  - tag: players
    method: GET
    path: /players/search
    summary: Search Players
    description: Searches players by partial username; returns an array of Player objects.
    query:
      - name: username
        type: string
        required: true
        description: partial username
      - name: limit
        type: integer
        required: false
      - name: offset
        type: integer
        required: false
    returns:
      content_type: application/json
      schema: Player[]

  - tag: players
    method: POST
    path: /players/{username}
    summary: Update a Player
    description: Tracks or updates a player; returns PlayerDetails (includes latest snapshot).
    path_params:
      - name: username
        type: string
        required: true
    returns:
      content_type: application/json
      schema: PlayerDetails

  - tag: players
    method: POST
    path: /players/{username}/assert-type
    summary: Assert Player Type
    description: Asserts (and attempts to fix) a player's game-mode type; returns { player, changed }.
    path_params:
      - name: username
        type: string
        required: true
    returns:
      content_type: application/json
      schema: { player: Player, changed: boolean }

  - tag: players
    method: GET
    path: /players/{username}
    summary: Get Player Details
    description: Fetches a player's details; returns PlayerDetails.
    path_params:
      - name: username
        type: string
        required: true
    returns:
      content_type: application/json
      schema: PlayerDetails

  - tag: players
    method: GET
    path: /players/{username}/groups
    summary: Get Player Group Memberships
    description: Fetches all of the player's group memberships; returns PlayerMembership[].
    path_params:
      - name: username
        type: string
        required: true
    query:
      - name: limit
        type: integer
        required: false
      - name: offset
        type: integer
        required: false
    returns:
      content_type: application/json
      schema: PlayerMembership[]

  - tag: players
    method: GET
    path: /players/{username}/archives
    summary: Get Player Archives
    description: Fetches archival history for a player; returns PlayerArchive[] (includes nested Player).
    path_params:
      - name: username
        type: string
        required: true
    returns:
      content_type: application/json
      schema: PlayerArchive[]

  # NOTE: The Players endpoints page contains many more endpoints (snapshots, gains, records, achievements, etc).
  # This file only includes the endpoints that were captured in the excerpts.

  # -----------------------------
  # Groups
  # -----------------------------
  - tag: groups
    method: GET
    path: /groups
    summary: Search Groups
    description: Searches groups by partial name; returns Group[].
    query:
      - name: name
        type: string
        required: false
      - name: limit
        type: integer
        required: false
      - name: offset
        type: integer
        required: false
    returns:
      content_type: application/json
      schema: Group[]

  - tag: groups
    method: DELETE
    path: /groups/{id}
    summary: Delete Group
    description: Deletes an existing group (irreversible). Requires a verification code in the body.
    path_params:
      - name: id
        type: integer
        required: true
    body:
      content_type: application/json
      fields:
        - name: verificationCode
          type: string
          required: true
    returns:
      content_type: application/json
      schema: object

  - tag: groups
    method: GET
    path: /groups/{id}/hiscores
    summary: Get Group Hiscores
    description: Returns group hiscores for a metric; docs note no maximum result limit.
    path_params:
      - name: id
        type: integer
        required: true
    query:
      - name: metric
        type: Metric
        required: true
      - name: limit
        type: integer
        required: false
      - name: offset
        type: integer
        required: false
    returns:
      content_type: application/json
      schema: array

  # -----------------------------
  # Competitions
  # -----------------------------
  - tag: competitions
    method: GET
    path: /competitions
    summary: Search Competitions
    description: Searches competitions by title/type/metric/status; returns Competition[].
    query:
      - name: title
        type: string
        required: false
      - name: metric
        type: Metric
        required: false
      - name: type
        type: CompetitionType
        required: false
      - name: status
        type: string
        required: false
        enum: [upcoming, ongoing, finished]
      - name: limit
        type: integer
        required: false
      - name: offset
        type: integer
        required: false
    returns:
      content_type: application/json
      schema: Competition[]

  - tag: competitions
    method: GET
    path: /competitions/{id}
    summary: Get Competition Details
    description: Returns CompetitionDetails including participants and progress.
    path_params:
      - name: id
        type: integer
        required: true
    returns:
      content_type: application/json
      schema: CompetitionDetails

  - tag: competitions
    method: POST
    path: /competitions/{id}/update-all
    summary: Update All (Outdated) Participants
    description: Attempts to update any outdated competition participants (see docs for rules).
    path_params:
      - name: id
        type: integer
        required: true
    returns:
      content_type: application/json
      schema: object

  # -----------------------------
  # Records
  # -----------------------------
  - tag: records
    method: GET
    path: /records/leaderboard
    summary: Get Global Record Leaderboards
    description: Fetches records leaderboard for a metric and period; returns RecordLeaderboardEntry[].
    query:
      - name: period
        type: Period
        required: true
      - name: metric
        type: Metric
        required: true
      - name: playerType
        type: PlayerType
        required: false
      - name: playerBuild
        type: PlayerBuild
        required: false
      - name: country
        type: Country
        required: false
    returns:
      content_type: application/json
      schema: RecordLeaderboardEntry[]

  # -----------------------------
  # Deltas
  # -----------------------------
  - tag: deltas
    method: GET
    path: /deltas/leaderboard
    summary: Get Global Delta Leaderboards
    description: Fetches top deltas leaderboard for a metric and period; returns DeltaLeaderboardEntry[].
    query:
      - name: period
        type: Period
        required: true
      - name: metric
        type: Metric
        required: true
      - name: playerType
        type: PlayerType
        required: false
      - name: playerBuild
        type: PlayerBuild
        required: false
      - name: country
        type: Country
        required: false
    returns:
      content_type: application/json
      schema: DeltaLeaderboardEntry[]

  # -----------------------------
  # Name Changes
  # -----------------------------
  - tag: name_changes
    method: GET
    path: /names
    summary: Search Name Changes
    description: Searches for name changes matching username and/or status; returns NameChange[].
    query:
      - name: username
        type: string
        required: false
      - name: status
        type: NameChangeStatus
        required: false
      - name: limit
        type: integer
        required: false
      - name: offset
        type: integer
        required: false
    returns:
      content_type: application/json
      schema: NameChange[]

  # -----------------------------
  # Efficiency
  # -----------------------------
  - tag: efficiency
    method: GET
    path: /efficiency/leaderboard
    summary: Get Global Efficiency Leaderboards
    description: Fetches efficiency leaderboard for a metric; returns Player[].
    query:
      - name: metric
        type: ComputedMetric|ehp+ehb
        required: true
      - name: playerType
        type: PlayerType
        required: false
      - name: playerBuild
        type: PlayerBuild
        required: false
      - name: country
        type: Country
        required: false
      - name: limit
        type: integer
        required: false
      - name: offset
        type: integer
        required: false
    returns:
      content_type: application/json
      schema: Player[]

---

## Notes for improving this into a full OpenAPI spec

- The official docs pages contain the full set of endpoints and full schemas.
- If you need a complete machine-readable spec, a robust approach is:
  1) crawl the docs pages for headings like "GET/..." and "POST/..." plus the parameter tables,
  2) map them into OpenAPI 3.0 paths,
  3) port the entities from the "Types & Entities" pages into components/schemas.
