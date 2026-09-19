# Workload publication ownership

## Summary

Owner: Orket Core. Date: 2026-09-19. Effective version: 0.6.35.
Affected contracts: SDK and legacy artifact publication, input capture and
interaction completion. Status: active; scoped source and installed proof is recorded in the canonical plan.

## Delta

Application retains admitted artifact workers through caller cancellation and
timeout. This covers root preparation, SDK artifact validation, manifest building
and writing, provenance building and writing, and final file digest observation.
Legacy registration, compilation, reliable-mode checks, validators and summary
callbacks also execute in owned workers. Loading, compilation and material
validation retain separate cancellation boundaries; an interrupted stage cannot
admit the next stage. The event loop remains available while
these synchronous operations run. Cancellation is propagated after the worker
settles; a worker failure takes precedence over cancellation. This is lifetime
ownership, not forced thread termination or a hard filesystem deadline.

Storage declares side effects and writes each JSON projection through a temporary
file in the same directory, flush/sync, replacement and exact closed-file readback.
Successful return requires verification. Failure may leave a completed file;
inspect retained artifacts rather than inferring that no effect occurred.
There is no transaction across files, control-plane records and interaction state,
nor new concurrency fencing for runs that select the same artifact directory.

Both executor entrypoints copy nested caller configuration and workload admission
records before their first await. Later caller mutation cannot change their
provenance. This does not freeze all ambient policy: reliable-mode, verbosity and
artifact-size environment reads still require the remaining explicit-input work.
Trusted legacy callback code can also retain its own mutable objects.

Cancellation before confirmed closeout preserves the existing unresolved execution
records. Cancellation after closeout leaves that recorded outcome authoritative.
A later provenance build/write/digest failure propagates its original exception
without attempting to replace confirmed execution success with failure. Partial
failure inside control-plane closeout remains a separate recovery obligation.
SDK validation failure uses the capability observations already published, including
their prior-step reference and observed side effects.

Extension execution no longer emits authoritative `TURN_FINAL` or requests a
duplicate finalization commit from a workload context. Those events are reserved
by the interaction lifecycle contract. `InteractionCommands` observes the returned
workload result and then asks its manager to finalize; failures enter its existing
fail-closed path. Direct executor embeddings return an `ExtensionRunResult` and
must delegate interaction finalization to their interaction owner.

## Migration Plan

1. Retired internal `workload_executor_support.write_json_file`, `digest_file` and
   `emit_turn_final_if_needed` have no forwarding aliases. Use application
   publication coordination; storage helpers alone do not own worker lifetime.
2. Legacy synchronous callbacks must not rely on running on the event-loop thread.
   Asynchronous interaction calls remain on the application event loop.
3. Direct context consumers must stop expecting the executor to author final
   lifecycle events. Use the application interaction manager after observing the
   result. JSON projection schemas and artifact paths are unchanged.
4. Required proof includes actual trusted SDK/legacy workloads, independent
   control-plane reads, held file workers, ordinary and repeated cancellation,
   caller timeout, native write refusal, captured inputs and real interactions.
   Fixed bounds are 0.5 seconds for responsiveness and 5 seconds for settlement
   after controlled release. Source and installed results must agree.

## Rollback Plan

Drain admitted workers before replacing owners and callers together. Preserve
control-plane records, projections and all failed proof. Do not replay uncertain
execution or reinterpret a missing provenance file as an unexecuted workload.
Rollback requires a new version and equivalent lifetime/interaction verification.

## Versioning Decision

Patch checkpoint 0.6.35. Internal publication imports and direct interaction
completion expectations change as described above. SDK wire formats and the SDK
package version remain unchanged. Full C/D/E/CAP acceptance remains open.
