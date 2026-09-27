# Required API event input capture

## Summary

- Owner: Orket Core, architectural-truth D.
- Date and target: 2026-09-25, v0.6.106 development candidate.
- Affected contract: `docs/specs/API_RUNTIME_LIFECYCLE.md`.
- Status: implementation contract; the canonical remediation plan owns proof and publication.

## Delta

`ApiEventService.emit` previously called `deepcopy` on the caller's event loop.
Custom values could therefore execute copy hooks before the retained publication
worker started. Later JSON encoding could also convert unsupported objects or
emit non-standard non-finite numbers.

The service now uses the pure `capture_log_event_inputs` contract before its
first await. Names and mapping keys must be exact built-in strings; the root
payload must be an exact built-in dictionary. Nested dictionaries, lists, tuples,
strings, integers, booleans, finite floats and `None` are admitted. Containers are
detached recursively; tuple shape is retained. Repeated references to an acyclic
value are allowed, but shared mutable identity is not retained across copies.

Subclasses, opaque objects, non-string keys, cycles, non-finite floats and values
deeper than the interpreter's recursion capacity raise
`TypeError("E_LOG_EVENT_INPUT_UNSUPPORTED")`. Type identity checks do not invoke
metaclass hashing/equality. No copy, conversion, representation, custom mapping,
iterator or serializer hook is used for capture. Rejection precedes admission
of the worker and any logging handler, path, file or subscriber effect.

The service still supplies its selected application root to the same
`run_owned_thread` operation and the same native `log_event` path exactly once.
Timestamp timing, native publication order, existing worker-failure precedence,
cancellation settlement and subscriber behavior remain. No queue, resource owner,
retry, fallback or application-owned logger shutdown is added. Callers must not
mutate inputs concurrently with synchronous capture; this is not an atomic
snapshot of an independently mutating object graph.

## Migration Plan

1. No compatibility window: programmatic callers normalize values at their own
   input authority before calling the service. HTTP-produced plain JSON values
   require no conversion or schema migration.
2. Do not add `default=str`, `deepcopy` or an arbitrary serializer fallback to
   accept an unsupported object. Existing persisted event records stay unchanged.
3. Require real API service rejection before effects, detached physical JSONL,
   the existing cancellation/shutdown/write-failure controls, exact installed
   regressions and the full successor acceptance matrix before publication.

## Rollback Plan

1. A hook invocation, unobserved worker, changed failure precedence or altered
   admitted JSON value blocks publication.
2. Correct capture through the same contract and worker; retain failed and
   passing observations. Do not reinstate caller-loop copy hooks.
3. Rejected input has no publication effect from this invocation. Existing
   partial native publication remains possible and is not rolled back.

## Versioning Decision

- Effective target: v0.6.106, unpublished development candidate.
- Plain JSON API behavior is preserved. Programmatic callers relying on custom
  Python values or non-finite numbers have an intentional input-contract break.
- This bounded change does not migrate the other required log producers or
  optional `log_event`, change logger preparation, acknowledge API handoffs,
  establish subscriber draining, or close whole-D/E/CAP acceptance.

## Proof scope

The 14 new controls and 37 existing API/logging/audit guards pass as an exact
51-case selection in fresh source and installed Windows Python 3.11/3.12. The
canonical plan binds failed openings, physical JSONL and no-effect observations,
package origins and owner settlement. This is local scoped proof; complete .106
acceptance and the wider logging correction remain open.
