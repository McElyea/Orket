# Builtin filesystem connector lifetime delta

## Summary

- Change title: Retain direct filesystem I/O until worker completion.
- Owner: Orket Core.
- Date: 2026-09-13.
- Affected contracts: `docs/specs/CONNECTOR_INVOCATION_TIMING.md` and
  `docs/specs/API_RUNTIME_LIFECYCLE.md`.

## Delta

- Current behavior: Bound outward filesystem effects drain their workers, but a
  direct connector can propagate cancellation or return timeout while its worker
  can still mutate a file. An owner awaiting that connector can settle too early.
- Proposed behavior: One adapter I/O owner serves bound and direct builtin
  filesystem invocations. Caller cancellation waits for the operation to settle;
  repeated cancellation does not release it. Timeout translation follows the same
  drain. The original exception/result remains available to the owner, and a
  failure during cancellation is logged. Command and HTTP lifetime contracts keep
  their separate meanings.
- Why this break is required now: BT-4 explicitly requires truthful lifetime
  semantics for thread-offloaded work. A completed cancelled await does not prove
  the underlying thread stopped.

## Migration Plan

1. Compatibility window: No new public method, schema or compatibility alias.
2. Migration steps: Extract the existing bound-I/O drain into one adapter helper
   and use it for the direct filesystem path. Keep authorization/path binding and
   effect journal behavior unchanged. Do not rewrite historical receipts.
3. Validation gates: Retain actual delayed-delete counterexamples for cancellation,
   repeated cancellation and timeout. Prove worker completion before return,
   actual filesystem state, bound-path parity and composed API shutdown. Preserve
   the frozen pre-change installed matrix as historical proof; run affected
   source and installed acceptance on the new candidate.

## Rollback Plan

1. Rollback trigger: Ownership loses exceptions, deadlocks settled I/O, weakens
   bindings, or returns before the admitted worker completes.
2. Rollback steps: Restore the preceding runtime and disclose direct filesystem
   lifetime as unsupported. Do not claim safe shutdown for that path.
3. Data/state recovery notes: Cancellation and timeout do not undo prior writes.
   Retain unresolved outward dispatch and existing evidence; never infer retry
   authority from a cancelled caller.

## Versioning Decision

- Version bump type: Patch candidate in the existing 0.6.x line; no release made.
- Effective version/date: Worktree implementation dated 2026-09-13.
- Downstream impact: Cancellation/timeout can wait longer for filesystem I/O.
  There is no forced thread termination, global shutdown deadline, detached-task
  ownership or abrupt-host-death guarantee. An indefinitely blocked operation
  remains pending rather than reporting confirmed cleanup.
