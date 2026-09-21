# Organization-loop ownership and selection

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version/date: 0.6.60 candidate, 2026-09-21.
- Contract: `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`.

## Delta
The published CLI loop attempts synchronous configuration loading on its event
loop and fails the existing file bridge. Direct loop execution can abandon its
scan worker and blocks the event loop during runtime construction. The scanner
also passes a model subdirectory where ConfigLoader requires a project root.

Provide async organization creation with captured construction inputs and an
owned configuration worker; refuse direct sync construction on the loop before
effects. Own scanning and reuse the shared runtime construction/required-close
boundary. Keep actual typed results and clear the running flag on exit.

Bind relative configuration and workspace paths to the captured project root,
retain loaded department values and supply captured environment to scanning.
Keep the existing missing-organization fallback. Correct cross-epic priority
ordering to consume the schema's numeric values after the existing ready-queue
weight. The old named-label map treated all normalized priorities as unknown;
two retained real-asset cases select LOW before HIGH before this correction.
The pure critical-path engine remains authoritative within each epic.

## Migration and rollback
CLI flags are unchanged. Async embeddings await `OrganizationLoop.create(...)`
before `run_forever()`, optionally supplying explicit `RuntimeConstructionInputs`.
Direct synchronous construction remains available before an event loop starts.
Its old async path already failed the file bridge; it now refuses before any
configuration observation. No compatibility shim or duplicate worker owner is
introduced. The legacy core critical-path shim is no longer used by this caller;
its separate governed retirement remains unchanged.

Each scan reads current authored assets, not a transaction across files or a
complete live database board. This change does not promise global optimal
scheduling or dispatch de-duplication. Partial resource acquisition by a failing
runtime constructor remains its responsibility. Remaining CLI engine/driver and
ConfigLoader bridge work stays separate. Rollback restores the documented
startup, selection and worker-lifetime defects and must disclose them.

## Versioning and verification
Compatible public patch with an explicit async embedding path. Require actual
authored selection, captured-root rotation, native CLI success/refusal, SQLite
publication and cancellation/timeout/failure/cleanup proof. Keep the predeclared
0.5-second response bound, worker deadlines, ten-second idle wait and accepted BT
evidence. Whole-suite, provider and Linux acceptance remain separate gates.
