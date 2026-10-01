# Retained checkpoint continuation identity

Owner: Orket Core
Date: 2026-09-28
Status: Implemented; five opening counterexamples retained, source closing passes
Contract: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`

## Delta

The turn checkpoint reader checked accepted resumability, action, continuation
target and starting snapshot but could return a decision belonging to another
run or failed attempt. Replacement lookup also omitted the checkpoint-parent
binding. Those retained records cannot authorize the requested continuation.

One pure validator in the existing checkpoint-authority module now binds the
requested run, resumed attempt, source attempt, recovery decision and checkpoint
parent. Same-attempt recovery uses itself as the source; replacement recovery
uses the already-selected prior attempt. Both existing branches call the same
validator and preserve other acceptance/action/snapshot checks. Inconsistent
identity raises `TurnToolCheckpointRecoveryError` without repair or new authority.
Other workload checkpoint-parent forms remain unchanged.

## Migration and rollback

No schema migration, new public entrypoint, compatibility shim or repair path is
added. Contradictory retained histories now refuse the reader instead of supplying
continuation authority. Operators must retain that evidence for existing recovery
procedures; this change does not authorize editing a stored decision.

The original failed-parent probes failed in both modes. Corrected and expanded
opening controls record 29 passes and five failures in 4.92s on Windows Python
3.11, with all 5,519 inputs unchanged. The failures are both decision-run variants,
both failed-parent variants and replacement checkpoint-parent mismatch. An earlier
fixture tried to mutate immutable admission through the repository; the repository
correctly refused. Its replacement explicitly corrupts validated retained rows
and keeps payload/index columns consistent, outside normal publication authority.

Opening evidence: `.tmp/goal-20260928-recovery-opening-v2-readback.json` and its
inputs/XML/log; the original v1 results remain retained. These are real SQLite
reader controls with metadata-only checkpoint references. They do not demonstrate
unauthorized end-to-end effects or valid artifact replay. Public callers retain
additional transaction, snapshot and approval checks. All 34 recovery controls
and selected real caller guards pass in the combined 278-case source closing
run, with all 5,520 inputs unchanged. Evidence:
`.tmp/goal-20260928-authority-recovery-closing-v1-readback.json` and its XML/log.

Reverting the two-file correction reopens this relational validation gap. Do not
weaken the refusal assertions or replace preserved histories to obtain acceptance.
The existing recovery file remains 423 lines and its lineage function remains
105 lines; this change does not widen that pre-existing size debt.

## Versioning

Patch-level correction on the dirty candidate after 0.6.114, effective date
2026-09-28. No version, release or stored-data migration is assigned here.
