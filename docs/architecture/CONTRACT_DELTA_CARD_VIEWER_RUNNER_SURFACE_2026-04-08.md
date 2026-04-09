# Contract Delta: Card Viewer/Runner Surface 2026-04-08

## Summary
- Change title: Add stable Card Viewer/Runner operator surface V1
- Owner: Orket Core
- Date: 2026-04-08
- Affected contract(s): `docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md`, `docs/API_FRONTEND_CONTRACT.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: UI clients had to bind raw `/v1/cards`, `/v1/runs`, and low-level run summary or artifact projections directly, inferring lifecycle, degradation, and verification state from technical fields.
- Proposed behavior: Orket now ships explicit operator read models behind `GET /v1/cards/view`, `GET /v1/cards/{card_id}/view`, `GET /v1/runs/view`, `GET /v1/runs/{session_id}/view`, `GET /v1/system/provider-status`, and `GET /v1/system/health-view`. `POST /v1/system/run-active` remains the canonical run/rerun action for this slice.
- Why this break is required now: the first serious cards UI needs one truthful, bounded read surface that does not require frontend artifact spelunking or ad hoc lifecycle inference.

## Migration Plan
1. Compatibility window: existing raw `/v1/cards`, `/v1/runs`, and `/v1/system/*` inspection routes remain available; the new `/view` routes are additive and are the canonical operator-facing surface for the first UI slice.
2. Migration steps:
   - bind cards and runs UI reads to the new `/view` routes
   - treat `lifecycle_category` and `filter_bucket` as the human-facing status source
   - use `POST /v1/system/run-active` for run/rerun actions
3. Validation gates:
   - `python -m pytest -q tests/interfaces/test_operator_view_models.py tests/interfaces/test_api_operator_views.py`
   - `python -m pytest -q tests/interfaces/test_api.py -k "runs_and_backlog_delegation or cards_endpoints_real_runtime_filters_and_pagination or cards_detail_history_comments_real_runtime or run_detail_and_session_status_real_runtime or run_detail_and_session_status_drop_invalid_run_summary_payload or run_detail_and_session_status_drop_invalid_run_artifact_projection"`
   - `python scripts/governance/check_docs_project_hygiene.py`

## Rollback Plan
1. Rollback trigger: operator view-model responses drift from the documented lifecycle vocabulary or route contract.
2. Rollback steps:
   - remove the `/view` routes and their supporting operator read-model builders
   - revert the same-change docs and authority sync
   - keep the existing raw inspection routes as the fallback operator surface
3. Data/state recovery notes: no persisted data migration is required; this is a projection-only read-surface addition over existing runtime, session, and run-ledger state.

## Versioning Decision
- Version bump type: additive contract surface
- Effective version/date: 2026-04-08
- Downstream impact: frontend and operator clients should prefer the new view routes for cards UI work; no raw route removal is included in this delta.
