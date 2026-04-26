# Contract Delta Proposal: NorthstarRefocus Phase 2 Approval and Execution Checkpoint

## Summary
- Change title: Outward-facing approval proposal queue, decision surface, and explicit write_file execution slice
- Owner: Orket Core
- Date: 2026-04-25
- Affected contract(s): `docs/API_FRONTEND_CONTRACT.md`, `docs/projects/archive/NorthstarRefocus/2026-04-25-OUTWARD-PIPELINE-CLOSEOUT/pipeline_requirements.md`

## Delta
- Current behavior: `/v1/approvals` primarily served the legacy Packet 1 approval surface, and the outward-facing pipeline had no persisted approval proposal queue, outward approval CLI, or execution path that paused before a governed tool effect.
- Proposed behavior: outward approval proposals are persisted separately, exposed through outward-aware `GET /v1/approvals`, `GET /v1/approvals/{approval_id}`, `POST /v1/approvals/{approval_id}/approve`, `POST /v1/approvals/{approval_id}/deny`, and compatibility `POST /v1/approvals/{approval_id}/decision`, with API-client-only `orket approvals list/review/approve/deny/watch` commands. `POST /v1/runs` also starts the explicit Phase 2 execution slice when `task.acceptance_contract.governed_tool_call` is present, pauses before an approval-required `write_file` effect, and applies that effect only after approval.
- Why this break is required now: Phase 2 needs a truthful operator-visible review and decision surface before run inspection, ledger export, and offline verification can be implemented.

## Migration Plan
1. Compatibility window: legacy Packet 1 approval list, detail, and decision behavior remains available when no matching outward approval proposal exists.
2. Migration steps: outward pipeline callers should use outward proposal ids and the explicit `approve` or `deny` endpoints; existing Packet 1 callers can keep using `/decision`.
3. Validation gates: targeted approval service, execution service, API, CLI, Phase 0/1 adjacent, and legacy approval compatibility tests.

## Rollback Plan
1. Rollback trigger: outward approval proposal persistence corrupts outward run state or breaks legacy Packet 1 approval behavior.
2. Rollback steps: remove outward approval service/store lookup from the approval router, remove the explicit outward execution service call from `POST /v1/runs` and approval resolution, and remove `orket approvals` CLI handlers while leaving Phase 0/1 outward run and `run_events` storage intact.
3. Data/state recovery notes: outward approval rows and proposal decision events are isolated in the control-plane SQLite database and can be ignored by legacy approval surfaces.

## Versioning Decision
- Version bump type: none in this working patch
- Effective version/date: 2026-04-25
- Downstream impact: additive API/CLI surface with legacy approval fallback preserved; explicit `write_file` execution now has approval-before-effect proof while broader connector hardening remains deferred to the connector phase.
