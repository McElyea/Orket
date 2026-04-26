# Contract Delta Proposal: NorthstarRefocus Phase 3 Run Inspection

## Summary
- Change title: Outward-facing run events, summary, and event stream surfaces
- Owner: Orket Core
- Date: 2026-04-25
- Affected contract(s): `docs/API_FRONTEND_CONTRACT.md`, `docs/projects/archive/NorthstarRefocus/2026-04-25-OUTWARD-PIPELINE-CLOSEOUT/pipeline_requirements.md`

## Delta
- Current behavior: outward runs could be submitted, approval-gated, and resolved, but operators had no outward-specific event history, derived summary, or event stream surface.
- Proposed behavior: outward run inspection is exposed through `GET /v1/runs/{run_id}/events`, `GET /v1/runs/{run_id}/summary`, polling-backed `GET /v1/runs/{run_id}/events/stream`, and API-client-only `orket run events/summary/watch` commands.
- Why this break is required now: Phase 3 needs read-only inspection before ledger export can truthfully package and verify the run history.

## Migration Plan
1. Compatibility window: legacy session-backed run detail, metrics, replay, backlog, and execution-graph endpoints remain available for non-outward run ids.
2. Migration steps: outward pipeline callers should use the outward `run_id` and the new event/summary/stream surfaces for persisted `run_events` inspection.
3. Validation gates: targeted inspection service, API, CLI, Phase 0/1/2 adjacent, and docs hygiene tests.

## Rollback Plan
1. Rollback trigger: outward inspection mutates state, exposes unfiltered operator payloads, or breaks existing run/session inspection.
2. Rollback steps: remove the outward event, summary, and stream endpoints plus `orket run events/summary/watch` CLI handlers while leaving Phase 0/1/2 outward persistence intact.
3. Data/state recovery notes: no new durable state family is introduced; inspection reads existing outward run and `run_events` rows only.

## Versioning Decision
- Version bump type: none in this working patch
- Effective version/date: 2026-04-25
- Downstream impact: additive API/CLI inspection surface with legacy run/session behavior preserved.
