# Card Viewer/Runner Surface V1

Last updated: 2026-04-08
Status: Active
Owner: Orket Core

## Purpose

Define the first truthful operator-facing cards UI slice.

This surface exists so cards, runs, provider status, and system health can be rendered from stable read models instead of direct raw run-summary or artifact parsing in the frontend.

## Canonical Routes

1. `GET /v1/cards/view`
2. `GET /v1/cards/{card_id}/view`
3. `GET /v1/runs/view`
4. `GET /v1/runs/{session_id}/view`
5. `GET /v1/system/provider-status`
6. `GET /v1/system/health-view`
7. `POST /v1/system/run-active` remains the canonical run or rerun action for the viewer slice.

## Canonical View Models

The admitted read models are:

1. `CardListItemView`
2. `CardDetailView`
3. `RunHistoryItemView`
4. `RunDetailView`
5. `ProviderStatusView`
6. `SystemHealthView`

Every admitted view model must include:

1. `primary_status`
2. `degraded`
3. `summary`
4. `reason_codes`
5. `next_action`

`reason_codes` are machine-readable operator-facing diagnostics.
`summary` is human-readable.
`next_action` is a stable operator action hint, not a guarantee that the runtime already succeeded.

## Lifecycle Outcome Vocabulary

The canonical terminal outcome vocabulary for run-facing operator views is:

1. `prebuild_blocked`
2. `artifact_run_failed`
3. `artifact_run_completed_unverified`
4. `artifact_run_verified`
5. `degraded_completed`

This vocabulary is human-facing lifecycle truth. It does not replace the existing technical fields on `run_summary.json`.

## Truth Rules

1. `artifact_run_verified` is admitted only when the run-facing verification summary records verified evidence. The shipped first slice uses `truthful_runtime_packet2.source_attribution.synthesis_status == verified`.
2. `artifact_run_completed_unverified` means the run completed, but the admitted verified-evidence condition above was not met.
3. `degraded_completed` means the run completed, but degraded summary or evidence state limits trust. This includes canonical degraded run summaries and degraded cards-runtime resolution states.
4. `prebuild_blocked` is admitted only when an ODR prebuild path stops before a primary artifact output exists.
5. The viewer may show `smoke` or `degraded` operator state, but it must not claim determinism proof or verified completion beyond the admitted evidence above.

## Card List Filters

`GET /v1/cards/view` admits the high-level filter tokens:

1. `open`
2. `running`
3. `blocked`
4. `review`
5. `terminal_failure`
6. `completed`

These filters are derived view buckets. They do not replace raw card status storage.

## Card Detail Requirements

`CardDetailView` must expose, at minimum:

1. issue identity and current raw card status
2. execution profile
3. artifact contract summary
4. the latest available run detail projection
5. explicit degraded state when present
6. a truthful run action descriptor that points to `POST /v1/system/run-active`

## Sync Rule

When the route set, lifecycle vocabulary, or required view-model fields change, update in the same change:

1. `docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md`
2. `docs/API_FRONTEND_CONTRACT.md`
3. `CURRENT_AUTHORITY.md`
