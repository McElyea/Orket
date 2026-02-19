# Frontend API Contract

Canonical GitHub URL:
`https://github.com/McElyea/Orket/blob/main/docs/API_FRONTEND_CONTRACT.md`

This repository copy is the source of truth used for code review and change tracking.
Prefer sharing the GitHub URL above instead of local filesystem paths.

Last verified against `orket/interfaces/api.py`: 2026-02-19.

## Purpose
Canonical API contract for dashboard/front-end workflows.

## Authentication and Transport
1. `/v1/*` endpoints are protected by API key validation.
2. Send API key in header: `X-API-Key: <key>`.
3. WebSocket stream endpoint is `WS /ws/events`.
4. WebSocket auth supports:
   - `X-API-Key` header, or
   - `api_key` query parameter.
5. Security policy note:
   - If `ORKET_API_KEY` is unset and `ORKET_ALLOW_INSECURE_NO_API_KEY` is enabled, `/v1/*` auth is bypassed.
   - Default posture is fail-closed without an API key.

## Core Health
1. `GET /health`
   - Response: `{ "status": "ok", "organization": "Orket" }`
2. `GET /v1/version`
3. `GET /v1/system/heartbeat`
4. `GET /v1/system/metrics`
5. `WS /ws/events`

## Run and Session Control
1. `POST /v1/system/run-active`
   - Request body:
   - `path` (optional)
   - `build_id` (optional)
   - `type` (optional)
   - `issue_id` (optional)
2. `GET /v1/runs`
3. `GET /v1/runs/{session_id}`
4. `GET /v1/runs/{session_id}/metrics`
5. `GET /v1/runs/{session_id}/token-summary`
6. `GET /v1/runs/{session_id}/backlog`
7. `GET /v1/runs/{session_id}/execution-graph`
8. `GET /v1/sessions/{session_id}`
9. `GET /v1/sessions/{session_id}/status`
10. `GET /v1/sessions/{session_id}/replay`
    - Query params:
    - `issue_id` (required)
    - `turn_index` (required)
    - `role` (optional)
11. `GET /v1/sessions/{session_id}/snapshot`
12. `POST /v1/sessions/{session_id}/halt`

## Sandboxes
1. `GET /v1/sandboxes`
2. `POST /v1/sandboxes/{sandbox_id}/stop`
3. `GET /v1/sandboxes/{sandbox_id}/logs`
   - Query param:
   - `service` (optional)

## Logs
1. `GET /v1/logs`
   - Query params:
   - `session_id` (optional)
   - `event` (optional)
   - `role` (optional)
   - `start_time` (optional ISO datetime)
   - `end_time` (optional ISO datetime)
   - `limit` (default `200`, max `2000`)
   - `offset` (default `0`)
2. `POST /v1/system/clear-logs`

## Cards
1. `GET /v1/cards`
   - Query params:
   - `build_id` (optional)
   - `session_id` (optional)
   - `status` (optional)
   - `limit` (default `50`, max `500`)
   - `offset` (default `0`)
2. `GET /v1/cards/{card_id}`
3. `GET /v1/cards/{card_id}/history`
4. `GET /v1/cards/{card_id}/guard-history`
5. `GET /v1/cards/{card_id}/comments`
6. `POST /v1/cards/archive`
   - Request body supports:
   - `card_ids` (optional)
   - `build_id` (optional)
   - `related_tokens` (optional)
   - `reason` (optional)
   - `archived_by` (optional, defaults to `api`)
   - At least one selector (`card_ids`, `build_id`, or `related_tokens`) is required.

## Runtime Policy and Settings
1. `GET /v1/system/runtime-policy/options`
2. `GET /v1/system/runtime-policy`
3. `POST /v1/system/runtime-policy`
4. `GET /v1/settings`
5. `PATCH /v1/settings`
6. `GET /v1/system/model-assignments`
   - Query param:
   - `roles` (optional CSV)
7. `GET /v1/system/teams`
   - Query param:
   - `department` (optional)

## System Utilities
1. `GET /v1/system/board`
2. `GET /v1/system/explorer`
   - Query param:
   - `path` (optional, defaults to `.`)
3. `GET /v1/system/read`
   - Query param:
   - `path` (required)
4. `POST /v1/system/save`
   - Request body:
   - `path`
   - `content`
5. `GET /v1/system/calendar`
6. `GET /v1/system/preview-asset`
   - Query params:
   - `path` (required)
   - `issue_id` (optional)
7. `POST /v1/system/chat-driver`
   - Request body:
   - `message`

## Replay UI Notes
1. Frontend timeline/list view is built from:
   - `GET /v1/logs` filtered to `event=turn_complete` and `session_id`.
2. Frontend detail view for a selected turn uses:
   - `GET /v1/sessions/{session_id}/replay?issue_id=<id>&turn_index=<n>&role=<optional>`.

## Frontend Critical Endpoints
These are the panel-critical routes currently expected by the frontend and are implemented:
1. `GET /v1/system/board`
2. `GET /v1/logs`
3. `GET /v1/runs/{session_id}/backlog`
4. `GET /v1/runs/{session_id}/execution-graph`
5. `GET /v1/runs/{session_id}`
6. `GET /v1/runs/{session_id}/metrics`
7. `GET /v1/sessions/{session_id}/status`
8. `GET /v1/sessions/{session_id}/replay`
9. `GET /v1/sandboxes`
10. `POST /v1/sandboxes/{sandbox_id}/stop`
11. `GET /v1/sandboxes/{sandbox_id}/logs`
12. `GET /v1/cards/{card_id}`
13. `GET /v1/cards/{card_id}/history`
14. `GET /v1/cards/{card_id}/comments`
15. `POST /v1/system/clear-logs`
16. `POST /v1/system/run-active`
17. `GET /v1/system/runtime-policy/options`
18. `GET /v1/system/runtime-policy`
19. `POST /v1/system/runtime-policy`
20. `GET /v1/settings`
21. `PATCH /v1/settings`
22. `POST /v1/sessions/{session_id}/halt`
