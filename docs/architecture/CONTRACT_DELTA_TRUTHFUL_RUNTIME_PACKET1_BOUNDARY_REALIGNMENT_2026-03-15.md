# Truthful Runtime Packet-1 Boundary Realignment Contract Delta

## Summary
- Change title: Packet-1 primary-boundary realignment and intended-path missing-token normalization
- Owner: Orket Core
- Date: 2026-03-15
- Affected contract(s): `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`

## Delta
- Current behavior: packet-1 may classify `agent_output/verification/runtime_verification.json` as the primary artifact boundary on successful runs, and finalize-path reconstruction may emit implementation-placeholder intended-path values such as `"unknown"` and `"None"`.
- Proposed behavior: packet-1 prefers an explicitly designated work artifact ahead of direct-response fallback, uses runtime verification only as a fallback boundary, and emits the stable token `missing` when required intended-path data is absent.
- Why this break is required now: the old behavior is truthful about the verification artifact but semantically misaligned with the operator-facing work product, and the placeholder provenance values are not acceptable long-lived truth-surface tokens.

## Migration Plan
1. Compatibility window: none; supersede the affected live proof candidates in the same change.
2. Migration steps:
   1. update the packet-1 contract and runtime selection logic
   2. freeze the `classification_basis` mapping in contract tests
   3. rerun and restage the packet-1 and packet-2 repair live proof candidates
   4. relabel the pre-fix proof artifacts as historical references only
3. Validation gates:
   1. contract and integration tests pass
   2. provider-backed packet-1 live proof passes with the new work-artifact boundary
   3. provider-backed packet-2 repair live proof passes with the new work-artifact boundary

## Rollback Plan
1. Rollback trigger: live proof rerun fails or the new boundary cannot be designated deterministically from runtime facts.
2. Rollback steps:
   1. revert the boundary-order and missing-token logic
   2. restore the prior staged proof candidates as current
   3. keep this delta record as abandoned if rollback occurs after publication
3. Data/state recovery notes: staged artifact supersession is file-level only; no durable runtime-state migration is required.

## Versioning Decision
- Version bump type: additive contract tightening with proof supersession
- Effective version/date: 2026-03-15
- Downstream impact: readers that treat packet-1 primary-output semantics as operator-facing should consume the superseding 2026-03-15 staged proof candidates until publication is explicitly approved.
