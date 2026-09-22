# Native synchronous coroutine ownership

Last updated: 2026-09-22
Status: Active implementation contract since 0.6.82; scoped acceptance belongs to the architectural-truth plan

Synchronous coroutine entrypoints require native execution. `run_coro_sync` refuses
a running event loop before scheduling its input. Async callers use the existing
owned worker boundary and retain it through cancellation, timeout and cleanup.
Await a native async API directly when one exists, such as Piper `synthesize_async`.
Calling a synchronous bridge on the event-loop thread is no longer supported.

The default bridge owns a fresh loop for that operation. It closes asynchronous
generators, cancels remaining tasks and drains the default executor before returning.
There is no global loop, daemon bridge thread or unmanaged thread-safe future.
Only an unstarted native coroutine object is admitted. On refusal, an unstarted
input is closed; a coroutine already started elsewhere is refused without taking
its ownership. Native guards report `E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER`.

Resources needing loop affinity use an explicit `SyncCoroutineOwner`. Calls on one
owner are serialized on the same loop, even when different native threads invoke
them. Each call copies its submitting context; the first caller's environment or
settings context does not become authority for later calls. The loop factory does
not replace the native caller's ambient event-loop binding. Owners are independent;
per-owner serialization is not a throughput or capacity acceptance claim.

Closing an owner stops admission before waiting for its active operation. Queued
operations refuse after acquiring the owner; newly submitted operations refuse
without waiting for that operation. A supplied finalizer runs once on the resource's
loop, followed by loop/generator/executor cleanup. Finalizer failure cannot skip
that cleanup. Reported loop/shutdown failures remain logged and visible to the close
caller. Operation and cleanup failures are retained together; repeated close cannot
turn a retained failed cleanup into success. A failed close is not proof of physical
resource cleanup. Arbitrary detached task results are not independently verified.

The SDK model provider owns one such loop. Generation and HTTP client cleanup use
that same loop; the provider stops admitting work when close begins. Async embeddings
offload and drain generation and close. The default API and extension owners retain
their existing provider ownership; borrowed providers remain their embedding's
responsibility. Construct a new provider after closure or failed closure.

SDK memory calls and synchronous Piper synthesis use the per-operation bridge.
Memory write/query/clear and model generate/close refuse before native work.
Piper voice discovery separately refuses with
`E_PIPER_DISCOVERY_REQUIRES_ASYNC_OWNER`. Review PR/diff/file entrypoints refuse with
`E_REVIEW_RUN_REQUIRES_ASYNC_OWNER` before policy, Git or transport work. Their native
Git/control-plane coroutine calls use per-operation owners.

Provider inventory imports the same bridge under its existing internal name, keeping
the governed 0.6.x module exports intact. Native inventory commands refuse an event
loop with `E_PROVIDER_INVENTORY_REQUIRES_ASYNC_OWNER`. This does not add descendant
supervision to those commands or establish live Ollama/LM Studio acceptance.

Owner closure is an ownership barrier, not a deadline or rollback guarantee. Existing
provider, command and test deadlines remain unchanged. The old five-second daemon
startup wait is obsolete because the bridge no longer starts a daemon thread.
Caller cancellation can follow real effects. Inspect retained state before retrying.

Acceptance requires real SQLite, controlled HTTP, Git/Piper process lifetimes,
repeated interruption, failure visibility and source/installed identity parity.
Independent SQLite retains the existing 0.5-second bound. Controlled HTTP is protocol
proof, not actual model inference. Linux clocks, physical sleep, complete adapter
and async inventories, remaining input owners, E/CAP and user acceptance remain open.
