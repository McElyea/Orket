# Native fatal failure settlement

## Summary
- Owner: Orket Core.
- Date: 2026-09-28.
- Contract: `docs/specs/SHARED_IO_CANCELLATION.md`.
- Status: implemented; six native closing controls and selected existing guards pass.

The subsequent nested-owner correction moves fatal containment to the existing
shared coroutine admission boundary while retaining these public native controls.
The leaf-only implementation described below is its historical predecessor:
`docs/architecture/CONTRACT_DELTA_NESTED_FATAL_IO_D_2026-09-28.md`.

## Delta
- Previous behavior: `run_owned_thread` awaited its native capability in an internal
  asyncio Task. A native `KeyboardInterrupt` or `SystemExit` can trigger that
  Task's fatal propagation into the loop runner before the public caller's error
  handling runs. Shielded gather alone does not contain that behavior.
- Changed behavior: a short native-await coroutine catches those two exception
  families before internal Task completion and returns the exact failure to the
  existing owned-I/O settlement. The existing failure selection then raises it
  at the public caller boundary. Failure identity and graph are retained; native
  failure still wins over caller interruption. This adds no settlement loop.
- Native cancellation, general operation-factory timing, coroutine-only admission,
  diagnostics, deadlines and partial effects retain their existing contracts.
  This is not general async fatal-task containment or logging preparation.

## Migration Plan
1. No public signatures, caller migration or compatibility layer.
2. Isolated children exercise `ApiEventService.emit` through real native standard
   handlers with both fatal exception types and normal/repeated-cancel/timeout
   callers. The caller catches inside its own coroutine. Require native identity,
   independent SQLite progress, resource close, continued sibling activity and a
   subsequent physically written event. Preserve failed predecessors and source
   origins. Existing admission/cancellation/diagnostic guards must remain green.
3. Both Quality selections retain the new integration module. Current-source and
   fresh installed/platform proof are separate observations. The unchanged-source
   opening exits its six owned children with the controlled fatal failures;
   the corrected six cases and existing guards pass in the 512-case Windows
   Python 3.11 closing run. All 5,509 inputs stayed unchanged; source-local evidence
   is `.tmp/goal-20260928-remediation-closing-v1-readback.json` and its XML/log.

## Rollback Plan
1. Reverting the narrow guard reopens the internal fatal propagation risk.
2. Preserve original failure receipts and rerun real child controls before
   accepting a replacement. Do not normalize fatal errors to successful results.
3. Earlier native effects can remain; no rollback or delivery guarantee is added.

## Versioning Decision
- Patch-level correction on the development candidate after 0.6.114.
- Proposed effective date: 2026-09-28; publication/versioning is separate.
- An unhandled fatal exception at the public caller boundary remains fatal.
