# Legacy extension action engine ownership

Status: active bounded D contract delta; whole-lane acceptance remains open.

Legacy `RunPlan` execution constructs its engine through the shared runtime owner
and requires engine close before returning either a result or a failure. The
owned worker drains construction through repeated cancellation and caller timeout.
An engine returned after interrupted construction is closed without executing an
action. The existing runtime action path retains its own execution semantics;
the surrounding owner also retains required cleanup through interruption.
Native construction or cleanup failure remains visible. Resources allocated and
discarded inside a failing constructor cannot be recovered by this returned-owner
protocol; no forced termination of a Python worker is promised.

Async embeddings use `async with ExtensionEngineAdapter.open(RunContext(...))`.
The factory captures invocation root, environment and settings before its owned
construction. Relative workspaces bind to that captured root. Direct synchronous
adapter construction now refuses an event-loop thread before engine effects with
`E_EXTENSION_ENGINE_REQUIRES_ASYNC_OWNER`. Pre-loop and worker construction remain
available, and those callers own `await adapter.close()`. This is a required
migration for direct async library callers. Canonical legacy workload execution
and repository contract callers use the owned context.

Compilation captures nested plan values before later material callbacks. Direct
action execution also captures its admitted plan before awaiting engine creation
or interaction events. Later mutations cannot rewrite dispatched parameters or
the returned plan hash. Legacy action aliases still normalize to `run_card`;
the shared runtime result projection remains the sole success check. Three
non-authoritative model observations retain their payloads and occur after engine
admission for nonempty plans. Empty plans retain those observations and create no
engine. Empty-plan success is not evidence of successful runtime action execution.

The outer workload control-plane lifecycle is unchanged. In particular, an
interrupted workload without confirmed terminal evidence remains executing with
no final truth; engine cleanup does not manufacture successful completion or a
confirmed no-effect terminal result. Actual CLI refusal/failure and SIGINT proof
records both the native exit and retained control-plane state. Synthetic action
results used in lifetime tests are explicit contract ports, not model or runtime
completion evidence.

This checkpoint does not complete ConfigLoader bridge migration, all direct
runtime constructors, broader captured inputs or async reachability. Trusted
extension admission, accepted BT authority, native deadlines and Linux clock
disposition remain unchanged. E1/E2, CAP and explicit user acceptance remain open.
Evidence and measured acceptance belong to the canonical remediation plan and
`.tmp/d-legacy-action-lifetime/`. Rollback must restore code and callers together;
unguarded event-loop construction reopens the documented defect.
