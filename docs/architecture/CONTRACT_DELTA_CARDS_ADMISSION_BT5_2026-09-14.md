# Cards epic control-plane admission transaction

## Summary
- Owner: Orket Core
- Date: 2026-09-14
- Contracts: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md` and
  `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`.
- Status: implemented; scoped source/installed and actual llama.cpp CLI proof
  pass in `.tmp/bt5-cards-admission/gate/audit.json`. Whole BT-5 remains open.

## Delta
- Previous behavior committed snapshots and a parent run before the initial
  attempt. An interrupted attempt write left an orphan parent on the composed
  cards path; outward and governed-agent controls rolled back.
- Cards epic admission now commits all of its control-plane admission records
  through the existing transaction factory before returning to epic dispatch.
  Exceptions and cancellation roll back snapshots, run/attempt, step, effect,
  checkpoint and acceptance together. No independent transaction owner is added.
- This is required by BT-5 shared admission consistency. Workload IDs, digests,
  effect authorization, checkpoint semantics and stored schemas are unchanged.

## Migration Plan
1. Stop older writers before adopting the repaired build; mixed writers cannot
   satisfy the new guarantee.
2. Preserve historical stores and orphan records. This change neither backfills
   attempts nor grants recovery/redispatch authority to incomplete history.
3. Validate shared family admission controls, all cards write boundaries with
   exceptions and cancellation, the existing family suite, installed packages,
   and separate actual llama.cpp CLI success and unsuccessful paths.

## Rollback Plan
1. Stop admission if transaction integrity or retained result consistency fails.
2. Preserve control-plane, runtime, acceptance and publication evidence. Repair
   forward; returning to non-atomic admission is not an accepted fallback.
3. The independent runtime/publication stores retain their current recovery
   contracts. No cross-store transaction or historical repair is claimed.

## Versioning Decision
- Patch-level behavioral repair in the existing uncommitted 0.6.2 candidate.
- No release, tag or push is performed by this change.
- Public call/result schemas are unchanged; downstream writers must honor the
  existing transaction ports and the new all-or-nothing admission boundary.
