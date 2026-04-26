# Contract Delta Proposal: NorthstarRefocus Phase 1 Run Submission

## Summary
- Change title: Outward-facing run submission and status surface
- Owner: Orket Core
- Date: 2026-04-25
- Affected contract(s): `docs/API_FRONTEND_CONTRACT.md`, `docs/projects/archive/NorthstarRefocus/2026-04-25-OUTWARD-PIPELINE-CLOSEOUT/pipeline_requirements.md`

## Delta
- Current behavior: `/v1/runs` was a legacy session/run inspection surface and the `orket` CLI had no outward-facing run submission commands.
- Proposed behavior: `POST /v1/runs` accepts a queued outward work submission, `GET /v1/runs` and `GET /v1/runs/{run_id}` return outward run status when outward records exist, and `orket run submit/status/list` delegates to those API surfaces.
- Why this break is required now: Phase 1 needs a stable submit/status/list loop before approval, event inspection, and ledger export phases can be implemented truthfully.

## Migration Plan
1. Compatibility window: legacy session-backed `GET /v1/runs` and `GET /v1/runs/{session_id}` remain available when no matching outward run record exists.
2. Migration steps: callers that need the outward pipeline should use `POST /v1/runs` or `orket run submit`; older runtime callers can continue existing session inspection paths.
3. Validation gates: targeted API, service, CLI, and legacy compatibility tests for run submission/status/list.

## Rollback Plan
1. Rollback trigger: outward run submission corrupts persisted state or breaks existing session/run inspection.
2. Rollback steps: remove `POST /v1/runs`, outward run-store lookups in existing run read endpoints, and `orket run` CLI handlers while leaving Phase 0 `run_events` storage intact.
3. Data/state recovery notes: queued outward run rows and `run_submitted` events are isolated in the control-plane SQLite database and can be ignored by legacy runtime surfaces.

## Versioning Decision
- Version bump type: none in this working patch
- Effective version/date: 2026-04-25
- Downstream impact: additive API/CLI surface with legacy read fallback preserved
