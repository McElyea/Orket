# Contract Delta Proposal: NorthstarRefocus Phase 4 Ledger Export

## Summary
- Change title: Outward-facing ledger export and offline verification
- Owner: Orket Core
- Date: 2026-04-25
- Affected contract(s): `docs/specs/LEDGER_EXPORT_V1.md`, `docs/API_FRONTEND_CONTRACT.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: outward pipeline runs can be submitted, approved, inspected, summarized, and streamed, but no canonical outward ledger export or offline verifier exists.
- Proposed behavior: outward `run_events` can be exported as `ledger_export.v1`; full exports verify from disclosed event payload bytes, filtered exports verify as partial views with canonical hash-chain anchors, and live `include_pii=true` exports record `ledger_export_requested` before serialization.
- Why this break is required now: Phase 4 is the next active NorthstarRefocus step and closes the operator loop from inspection to export and offline verification without promoting legacy artifacts into ledger authority.

## Migration Plan
1. Compatibility window: additive v1 API and CLI surfaces; existing run, approval, and inspection paths remain unchanged.
2. Migration steps: clients that need export/verify use `GET /v1/runs/{run_id}/ledger`, `GET /v1/runs/{run_id}/ledger/verify`, or `orket ledger export/verify/summary`.
3. Validation gates: focused application, API, and CLI tests cover full export verification, tamper detection, partial-view verification, audit-event recording, and outbound policy-gate traversal.

## Rollback Plan
1. Rollback trigger: ledger export or verifier produces false valid results, mutates event payload authority incorrectly, or records incorrect audit events.
2. Rollback steps: remove the Phase 4 ledger endpoints and CLI commands, stop calling `OutwardLedgerService`, and leave already-written `event_hash` and `chain_hash` columns as inert stored values until a corrected backfill/export implementation lands.
3. Data/state recovery notes: Phase 4 does not import legacy artifacts or alter event payloads. If rollback is needed, outward `run_events` payload authority remains intact.

## Versioning Decision
- Version bump type: none in this worktree change.
- Effective version/date: 2026-04-25.
- Downstream impact: frontend and operator clients may consume additive ledger export and verify surfaces; offline verification must use the `ledger_export.v1` contract.
