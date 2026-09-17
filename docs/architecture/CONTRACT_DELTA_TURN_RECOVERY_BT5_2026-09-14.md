# Governed turn recovery transaction

## Summary
- Owner: Orket Core
- Date: 2026-09-14
- Contract: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`
- Status: scoped source, installed and native acceptance passes; broader BT-5 remains open.

## Delta
- Turn recovery previously committed attempt, run, recovery, reconciliation,
  terminal truth and lease writes independently. Twelve real SQLite controls fail
  rollback after a write exception or cancellation: ten retain partial state and
  two retain completed closure after the final write reports failure. A healthy
  closure control passes. Evidence: `.tmp/bt5-turn-recovery-atomic/before-checked.xml`
  and `before-observations.json` in the same directory.
- Application service and workflow entrypoints now use the existing transaction
  factory through `turn_tool_recovery_transaction.py`. The retained algorithms
  operate on borrowed repositories under that owner. Current run/attempt must
  match captured caller inputs; orphan-artifact recovery also compares checkpoint
  and acceptance under the same writer transaction.
- A completed reconciliation refusal commits its blocked outcome before raising
  the existing recovery-error subtype. Other failures and cancellation roll back
  recovery writes. Physical effects and prior evidence remain retained.
- This is local control-plane transaction authority. It does not supply a fence
  across model/tool work, atomic filesystem/SQLite publication, historical repair,
  or general run-state CAS for other callers.

## Migration Plan
1. Stop old writers before installing; incompatible mixed writers are unadmitted.
2. Preserve partially written historical stores and original evidence. This change
   does not rewrite or automatically resume interrupted historical recovery.
3. Verify source and installed family controls, orphan/effect interruption,
   stale authority, checkpoint resume and actual llama.cpp CLI regression paths.
   The accepted audit is `.tmp/bt5-turn-recovery-atomic/gate/audit.json`: 1,150 cases
   pass in source and each Windows/Linux Python 3.11/3.12 installed environment,
   with 30 recovery controls, exact package/input checks and native CLI regression.

## Rollback Plan
1. Stop recovery admission when retained authority conflicts or cleanup fails.
2. Preserve databases, lease/effect history and artifacts; repair forward.
3. Do not restore independent writes or erase history to permit redispatch.

## Versioning Decision
- Behavioral repair in the uncommitted core 0.6.2 candidate.
- Stored schemas and successful public responses remain unchanged; internal
  callers now pass the explicit transaction factory.
- No commit, release, tag or push is performed by this repair.
