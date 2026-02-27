# Frontend API Contract

Last verified against `orket/interfaces/api.py`: 2026-02-27

## Authentication
1. `/v1/*` endpoints require `X-API-Key`.
2. Websocket endpoint `GET ws://<host>/ws/events` accepts API key via:
   - `X-API-Key` header, or
   - `api_key` query parameter.
3. Fail-closed default: requests are rejected when `ORKET_API_KEY` is unset.
4. Insecure bypass exists only when `ORKET_ALLOW_INSECURE_NO_API_KEY=true`.

## Base Health
1. `GET /health`
2. `GET /v1/version`
3. `GET /v1/system/heartbeat`
4. `GET /v1/system/metrics`
5. `WS /ws/events`

## Kernel Endpoints
1. `POST /v1/kernel/lifecycle`
2. `POST /v1/kernel/compare`
3. `POST /v1/kernel/replay`

## Runtime Control and Introspection
1. `POST /v1/system/run-active`
2. `GET /v1/runs`
3. `GET /v1/runs/{session_id}`
4. `GET /v1/runs/{session_id}/metrics`
5. `GET /v1/runs/{session_id}/token-summary`
6. `GET /v1/runs/{session_id}/replay`
7. `GET /v1/runs/{session_id}/backlog`
8. `GET /v1/runs/{session_id}/execution-graph`
9. `GET /v1/sessions/{session_id}`
10. `GET /v1/sessions/{session_id}/status`
11. `GET /v1/sessions/{session_id}/replay`
12. `GET /v1/sessions/{session_id}/snapshot`
13. `POST /v1/sessions/{session_id}/halt`

## Files and System Utilities
1. `GET /v1/system/explorer`
2. `GET /v1/system/read`
3. `POST /v1/system/save`
4. `GET /v1/system/calendar`
5. `GET /v1/system/board`
6. `GET /v1/system/preview-asset`
7. `POST /v1/system/chat-driver`
8. `GET /v1/logs`
9. `POST /v1/system/clear-logs`

## Cards
1. `GET /v1/cards`
2. `GET /v1/cards/{card_id}`
3. `GET /v1/cards/{card_id}/history`
4. `GET /v1/cards/{card_id}/guard-history`
5. `GET /v1/cards/{card_id}/comments`
6. `POST /v1/cards/archive`

## Sandboxes
1. `GET /v1/sandboxes`
2. `POST /v1/sandboxes/{sandbox_id}/stop`
3. `GET /v1/sandboxes/{sandbox_id}/logs`

## Runtime Policy and Settings
1. `GET /v1/system/runtime-policy/options`
2. `GET /v1/system/runtime-policy`
3. `POST /v1/system/runtime-policy`
4. `GET /v1/system/model-assignments`
5. `GET /v1/system/teams`
6. `GET /v1/settings`
7. `PATCH /v1/settings`

## Query/Body Notes
1. `GET /v1/logs` supports: `session_id`, `event`, `role`, `start_time`, `end_time`, `limit`, `offset`.
2. `GET /v1/sessions/{session_id}/replay` requires: `issue_id`, `turn_index`; optional `role`.
3. `POST /v1/cards/archive` requires at least one selector: `card_ids`, `build_id`, or `related_tokens`.
4. `POST /v1/system/run-active` body supports: `path`, `build_id`, `type`, `issue_id`.
5. `PATCH /v1/settings` accepts runtime setting updates defined in `SETTINGS_SCHEMA`.

## Compatibility Rule
When routes or payload shapes change, update this document in the same PR.
