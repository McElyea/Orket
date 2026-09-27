# Supporting failure diagnostic ownership

## Summary
- Change title: Retain supporting failure diagnostics without abandoning cleanup.
- Owner: Orket Core.
- Date: 2026-09-27.
- Status: Accepted for implementation after reproduced openings; closing proof pending.
- Affected contracts: `RUNTIME_FAILURE_DIAGNOSTICS.md`, `API_RUNTIME_LIFECYCLE.md`,
  and `CONTRACT_DELTA_RUNTIME_RESOURCE_CLEANUP_D_2026-09-21.md`.

## Delta
- Current cancellation, preparation and close supervisors synchronously invoke
  standard handlers on the event loop. A handler failure can replace the selected
  native failure or escape before later acquired resources are closed.
- Accepted change: use one diagnostic-settlement capability backed by the existing native
  task/worker owner. It retains the native attempt, avoids recursive reporting, and
  adds only the fixed `E_OWNED_DIAGNOSTIC_FAILED` note when that supporting attempt
  fails. It preserves the primary exception and existing cancellation precedence.
- This assumes ordinary borrowed exception state with a normal notes list.
  Direct `BaseException.add_note` bypasses public method overrides; existing notes
  remain and the fixed marker is additive. Hostile attribute hooks, malformed notes
  and concurrent external mutation are outside scope without a compatibility path.
- Capture bound logger methods/context and explicit exception triples; do not copy
  resources or rely on worker-local `exc_info=True` to rediscover the exception.
- API preparation/cleanup and nested runtime cleanup continue all declared close
  attempts. Managed background diagnostics remain within their existing tracked
  task while failed admission is visible immediately. No untracked task or second
  logging owner is introduced.
- This break is required because a diagnostic failure must not manufacture a
  replacement outcome or bypass previously admitted resource cleanup.

## Migration Plan
1. No compatibility shim. Affected custom standard handlers must support worker
   thread invocation; their logger identity remains borrowed.
2. Consumers retain the same primary/native exception and current cleanup aggregate
   shape. Inspect the stable note to identify unavailable supporting diagnostics;
   it contains no secret-bearing text or secondary exception object.
3. Preserve source/installed regressions for native I/O failure precedence, API
   construction/startup/shutdown and runtime cleanup. Add the held/failing-handler
   opening/closing controls before claiming scoped acceptance.

## Rollback Plan
1. Stop adoption if ownership, primary precedence or peer cleanup controls fail;
   preserve failure receipts and affected resource state.
2. Revert owner and callsite changes together, with the synchronous diagnostic and
   skipped-cleanup defects disclosed. Do not treat diagnostic silence as success.

## Versioning Decision
- Version bump type: patch, at a later architectural-truth checkpoint.
- Target recorded in 0.6.109 dated 2026-09-27; implementation remains pending and
  its effective runtime version is unassigned. This checkpoint changes no runtime
  diagnostic behavior and introduces no handler migration yet.
- Downstream impact: supporting diagnostics execute natively and can no longer
  replace a primary failure. No optional logging, delivery, rollback, process-stop,
  synchronous close-port or whole-lane guarantee is added.
