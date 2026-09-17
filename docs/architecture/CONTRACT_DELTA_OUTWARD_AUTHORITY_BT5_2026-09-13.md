# Outward shared authority cutover

## Summary
- Owner: Orket Core, architectural-truth BT-5.
- Date: 2026-09-13.
- Contract: `docs/specs/OUTWARD_RUN_AUTHORITY.md`.
- Status: scoped shared outward cutover accepted 2026-09-14; BT-5 remains open.

## Delta
- Outward admission uses canonical workload identity and shared run/attempt
  snapshots in its existing SQLite transaction.
- One evidence-derived final-truth publisher replaces separate terminal writes.
  Denial and expiry publish terminal truth in the decision transaction.
- Run API projections include `authority_state` and shared `final_truth`; their
  digest is committed in terminal events. Historical protocol status remains
  distinct from result classification.
- Frozen input drift is rejected earlier by shared admission, using
  `E_OUTWARD_AUTHORITY_INPUT_DRIFT` instead of a later model/effect-specific error.
- Older generation-one runs need an explicit authority migration. Generation-zero
  quarantine and all existing effect/recovery bindings remain active.

## Migration Plan
1. Preserve old-wheel databases, artifacts, approval bindings and recovery fences.
2. The implemented `orket.interfaces.outward_authority_cli` inspects and adopts one
   reviewed retained run under a writer lock, with an expected digest and explicit
   stopped-owner attestation. Its admission event identifies current-state input
   adoption; mutable old rows are not proof of original submission.
3. Prove copied pending and terminal histories, invalid-history refusal,
   interruption/restart and idempotence before accepting this cutover.
4. Preserve retained old events and shared journal entries without dual dispatch.
5. Source CLI copies of four terminal and seven unfinished old installed histories
   pass migration and repeat preservation. Source application continuation and
   fenced recovery also pass on fresh old-wheel histories. Native migration
   interruption/restart passes with the ledger reader on the writer connection;
   installed Windows/Linux Python 3.11/3.12 migration and continuation now pass,
   as do separate actual installed llama.cpp success/denial/expiry/policy-rejection
   paths. Artifact and retained-hash acceptance is recorded in the canonical plan.
   Whole-family conformance remains open.

## Rollback Plan
1. Stop new admission if the shared transaction regresses.
2. Preserve all old and new retained authority; do not delete snapshots or final truth.
3. Do not resume an old writer against a migrated live store to bypass fencing.

## Versioning Decision
- Current 0.6.2 worktree candidate only; no release, commit or tag in this change.
- Follow contributor release policy when integrating the fully accepted candidate.
