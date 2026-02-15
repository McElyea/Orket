# Frontend API Contract

Last updated: 2026-02-15.

## Purpose
Canonical API contract for dashboard/front-end workflows.

## Authentication
1. `/v1/*` requires `X-API-Key`.
2. Live stream endpoint is `/ws/events`.

## Core Workflows

### 1. Runtime Health and Controls
1. `GET /health`
   - Response: `{ "status": "ok", "organization": "Orket" }`
2. `GET /v1/system/heartbeat`
   - Response: `{ "status": "online", "timestamp": "<iso>", "active_tasks": <int> }`
3. `POST /v1/system/run-active`
   - Request:
   ```json
   {
     "path": "model/core/epics/standard.json",
     "build_id": "build-123",
     "type": "epic"
   }
   ```
   - Response:
   ```json
   {
     "session_id": "abcd1234"
   }
   ```

### 2. Past Run Inspection
1. `GET /v1/runs`
   - Returns recent run/session rows.
2. `GET /v1/runs/{session_id}/metrics`
   - Returns per-member metrics for a run.
3. `GET /v1/runs/{session_id}/backlog`
   - Returns issue/card rows linked to `session_id`.
4. `GET /v1/runs/{session_id}`
   - Returns run detail with:
     - `status`
     - `summary`
     - `artifacts`
     - `issue_count`
     - `session`
     - `run_ledger`
5. `GET /v1/sessions/{session_id}`
   - Returns session details (status, transcript, timestamps).
6. `GET /v1/sessions/{session_id}/snapshot`
   - Returns stored snapshot payload for a session.
7. `GET /v1/sessions/{session_id}/status`
   - Pollable status payload including:
     - `active`
     - `task_state`
     - backlog counts by status
     - run summary/artifacts

### 3. Logs
1. `GET /v1/sandboxes/{sandbox_id}/logs?service=<optional>`
   - Returns sandbox log text for service-level views.
2. `GET /v1/system/metrics`
   - Returns host metrics for live monitoring cards.
3. `WS /ws/events`
   - Pushes runtime event/log records in real time.

### 4. Cards
1. `GET /v1/cards`
   - Query params:
     - `build_id` (optional)
     - `session_id` (optional)
     - `status` (optional)
     - `limit` (default `50`, max `500`)
     - `offset` (default `0`)
   - Response:
   ```json
   {
     "items": [],
     "limit": 50,
     "offset": 0,
     "count": 0,
     "filters": {
       "build_id": null,
       "session_id": null,
       "status": null
     }
   }
   ```
2. `GET /v1/cards/{card_id}`
   - Returns card detail payload from persistence.
3. `GET /v1/cards/{card_id}/history`
   - Returns transaction timeline entries.
4. `GET /v1/cards/{card_id}/comments`
   - Returns persisted card comments.

### 5. Runtime Policy and Settings (Current Surface)
1. `GET /v1/system/runtime-policy/options`
2. `GET /v1/system/runtime-policy`
3. `POST /v1/system/runtime-policy`
   - Current editable settings:
     - `architecture_mode`
     - `frontend_framework_mode`
     - `project_surface_profile`
     - `small_project_builder_variant`
     - `state_backend_mode`
     - `gitea_state_pilot_enabled`

## Planned Expansions
1. Dedicated settings endpoint family (`/v1/settings`).
2. Dedicated historical log query endpoints (`/v1/logs`).

## Orchestration Controls
1. `POST /v1/sessions/{session_id}/halt`
   - Request loop/task cancellation for an active session.
2. `GET /v1/sessions/{session_id}/replay?issue_id=<id>&turn_index=<n>&role=<optional>`
   - Returns replay diagnostics for a specific turn from observability artifacts.
