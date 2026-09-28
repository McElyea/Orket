# Supporting failure diagnostic ownership

## Summary
- Change title: Retain supporting failure diagnostics without abandoning cleanup.
- Owner: Orket Core.
- Date: 2026-09-27.
- Status: Implemented; copied-source and current-source closing proof passed, current installed acceptance pending.
- Affected contracts: `RUNTIME_FAILURE_DIAGNOSTICS.md`, `API_RUNTIME_LIFECYCLE.md`,
  and `CONTRACT_DELTA_RUNTIME_RESOURCE_CLEANUP_D_2026-09-21.md`.

## Delta
- Previous cancellation, preparation and close supervisors synchronously invoked
  standard handlers on the event loop. A handler failure can replace the selected
  native failure or escape before later acquired resources are closed.
- Implemented change: use one diagnostic-settlement capability backed by the existing native
  task/worker owner. It retains the native attempt, avoids recursive reporting, and
  adds only the fixed `E_OWNED_DIAGNOSTIC_FAILED` note when that supporting attempt
  fails. It preserves the primary exception and existing cancellation precedence.
- The native diagnostic boundary contains even fatal handler exceptions before
  its asyncio task completes. Executor refusal is also a supporting failure;
  neither replaces the already selected primary exception.
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
- Managed command-cleanup uncertainty is normalized once. Diagnostic, admission
  and teardown retain that object, without counting its draining diagnostic as a
  second failed owner.
- This break is required because a diagnostic failure must not manufacture a
  replacement outcome or bypass previously admitted resource cleanup.

## Migration Plan
1. No compatibility shim. Affected custom standard handlers must support worker
   thread invocation; their logger identity remains borrowed.
2. Consumers retain the same primary/native exception and current cleanup aggregate
   shape. Inspect the stable note to identify unavailable supporting diagnostics;
   it contains no secret-bearing text or secondary exception object.
3. Both Quality jobs retain the held/failing-handler, fatal-handler and executor
   refusal controls with native I/O, API construction/startup/shutdown and runtime
   cleanup guards. Preserve exact source/installed proof boundaries.

## Rollback Plan
1. Stop adoption if ownership, primary precedence or peer cleanup controls fail;
   preserve failure receipts and affected resource state.
2. Revert owner and callsite changes together, with the synchronous diagnostic and
   skipped-cleanup defects disclosed. Do not treat diagnostic silence as success.

## Versioning Decision
- Version bump type: patch; effective runtime candidate 0.6.110.
- The accepted target was recorded in 0.6.109 dated 2026-09-27. The 0.6.110
  candidate implements native supporting diagnostics and the handler migration.
- Windows Python 3.11 copied-source closing proof passed 28 controls and 66
  existing guards. That copy declared 0.6.109 with interpreter distribution
  metadata 0.6.108. Current source with editable 0.6.110 metadata also passes the
  same 94 cases. Fresh installed, full-suite and Linux acceptance remain pending.
  Synthetic command-lifetime inputs prove observation identity,
  not native command cleanup.
- Downstream impact: supporting diagnostics execute natively and can no longer
  replace a primary failure. No optional logging, delivery, rollback, process-stop,
  synchronous close-port or whole-lane guarantee is added.
