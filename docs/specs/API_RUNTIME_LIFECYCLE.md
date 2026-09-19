# API Runtime Lifecycle

Last updated: 2026-09-18
Status: Active

`orket.application.services.api_runtime_container.ApiRuntimeContainer` owns the
HTTP/WebSocket ASGI invocation tasks, registered background tasks and resources
of one API application, followed by its engine. The public factory is
`orket.interfaces.runtime_entrypoints.create_api_app(CompositionConfig)`;
`orket.interfaces.api.lifespan` delegates initialization and teardown to
`orket.application.services.api_startup_service.api_runtime_lifespan`.

API and standalone webhook owners share `ApplicationRuntimeLifetime`; their
configuration and final resources remain separate. Managed background work uses
`start_background`, which retains failures even when work finishes before close.
Unexpected background failure stops new admission and prevents a clean teardown
claim. Existing manually registered API tasks keep their registration contract.

Startup captures the engine, authentication, state, root and governed-agent owner
before awaiting. Initialization is an admitted invocation: concurrent close cancels
and drains it before resources and the engine. Root validation uses an owned file
worker. The event broadcaster receives captured state/strategy inputs and uses
managed background admission; it never reacquires the app context after close.
Its delivery failure releases queue bookkeeping, closes new admission and remains
observable at teardown even when the task has already finished. A registered
subscription resource unsubscribes after admitted work settles. Startup no longer
creates an unused invocation-level `logs/` directory; actual log publication still
creates its own destination parent.

The startup posture's `insecure_no_api_key_bypass` describes effective anonymous
authentication, not merely the presence of the environment flag. A configured key
still rejects anonymous/wrong-key access when that flag is set. Production/staging
still reject the insecure flag at startup. These semantics do not make all manually
registered API background tasks managed or impose a startup/shutdown deadline.

## Factory and storage selection

The admitted API, CLI and webhook factories live in
`orket.interfaces.runtime_entrypoints`; application owns `CompositionConfig`,
engine construction and capability authorization. Migration from the retired
runtime factory exports is recorded in
`docs/architecture/CONTRACT_DELTA_INTERFACE_COMPOSITION_C_2026-09-18.md`.

Distinct applications and project roots do not imply distinct persistent stores.
The existing runtime database default is invocation-relative, as specified by
`docs/specs/RUNTIME_STORE_BINDING.md`. Applications constructed with the same
durable-root selection share card history. To select separate stores, supply a
different `ORKET_DURABLE_ROOT` before each factory invocation; an engine retains
its resolved absolute binding. Do not change process environment concurrently
with construction. This is existing storage behavior, not a tenant-isolation
guarantee or an automatic database migration.

## Captured authority and system observations

Authentication, startup security and CORS share the application's captured settings.
HTTP and both WebSocket routes delegate to application authentication, not a
replaceable strategy. Rotation requires constructing a new application. Calendar
baseline/timezone are captured per app and system timestamps use its runtime clock.
Board/metrics observations select the app root. Explorer, board and metrics workers
retain ownership through cancellation and elapsed caller timeout; shutdown waits
for admitted observations, and worker errors remain failures. This adds no OS
containment, forced worker termination or shutdown deadline. Migration:
`docs/architecture/CONTRACT_DELTA_API_AUTHORITY_INPUTS_CD_2026-09-17.md`.

## Admission and completion

1. `accepting_work` becomes false when the first `close()` starts. Task/resource
   registration, request invocation admission and API runtime-context lookup reject
   new work from that point. HTTP requests receive 503, including `/health`.
   WebSockets are closed before acceptance; established sockets close with 1001.
   Rejected task registration retains its existing cancel-and-raise behavior;
   callers must not create unowned work before registration.
2. One retained teardown task serves all close callers. Concurrent callers await
   it; repeated cancellation of a caller does not cancel that shared operation.
   After successful teardown, the cancelled caller receives its cancellation.
3. `closed` means the owned task and registered resource teardown completed
   successfully. It remains
   false while closing and after failure. It does not mean a cancelled workload
   succeeded, durable publication completed, or every external effect stopped.
4. Teardown cancels and awaits request and background tasks active at its start, closes
   registered resources in reverse order, then closes the engine. Resource close
   methods must report failure and own their cleanup; asynchronous methods are
   awaited, and synchronous close methods must not block the event loop.
   The container records its own cancellation request once per task, shared by
   request-disconnect and shutdown paths. A task's existing cancellation count
   may belong to an internal timeout and does not establish owner cancellation.
   Shutdown does not issue a second owner cancellation into cleanup already
   requested by a disconnected request waiter.
5. Failed request/background teardown, explicitly unconfirmed native command cancellation,
   resource failure/cancellation, and engine failure prevent a successful close.
   Failures are logged with owner context. Peer resources and the engine still
   receive close attempts. The aggregate `RuntimeError` retains the first cause.
6. Teardown failure takes precedence over a close caller's cancellation. Every
   later close observes the same retained failure; it does not silently retry
   partially completed effects. Successful repeated close also works after the
   original event loop ends. Pending teardown belongs to its original loop.
7. An owned request, a descendant inheriting that request's context, an owned
   background task or the teardown task cannot await its own close.
   That call raises instead of deadlocking. Lifespan relinquishes its event
   subscription and lets the container close the tracked broadcaster with peers.
8. `run_request` admits before constructing an invocation. Pure ASGI middleware
   keeps ownership through response bodies and awaited connector execution;
   `active_request_count` reports unfinished invocation tasks. Lifespan is outside
   request ownership. Cancellation of a request waiter cancels its invocation once
   and waits for cleanup, even when the waiter receives repeated cancellation.
   Request and close waiters consume the same retained cleanup observation.
9. Shutdown cancellation before HTTP headers yields 503. After headers, the
   response is truncated and the server terminates the transport; the middleware
   cannot replace an already sent status. Event and interaction WebSockets release
   their registrations during cancellation. Normal `/v1/` responses and shutdown
   503 responses retain `X-Orket-Version`.

## Extension model generation

The generic extension generation route retains its synchronous SDK worker until
generation and request-owned client cleanup settle. Caller cancellation, including
repeated cancellation and container shutdown, does not detach that worker. A
successful worker result after cancellation is discarded and cancellation propagates;
it does not become a successful HTTP response. A worker or cleanup failure takes
precedence and remains observable to request and shutdown owners. The shared
`run_owned_thread` delegates to the shared
`run_owned_io(..., preserve_failure=True)` seam for that ordering; existing
connector callers retain their established default error/cancellation behavior.

Provider/model overrides construct a separate builtin client with an explicit
provider argument. They never temporarily mutate `ORKET_LLM_PROVIDER` or
`ORKET_MODEL_PROVIDER`. The worker closes that client on its persistent SDK bridge
loop before it settles. Constructor/provider validation errors propagate without
fallback. The existing model-only/default-model selection contract is unchanged.

The application registers `ExtensionRuntimeService` as a resource. After admitted
requests settle, its close offloads and drains cleanup of the builtin model client
that the service constructed. That client closes on the same bridge loop used by
generation, and its adapter rejects subsequent generation. Injected providers
remain owned by the embedding caller; their synchronous generation is drained,
but the service does not close them or reconstruct their override settings.
Direct embeddings must stop admission and await their calls before closing the
service. Other extension capabilities are outside this model-client close scope.

This is local lifetime ownership, not an inference interrupt or a shutdown deadline.
A blocked worker can keep cancellation/shutdown pending. Closing HTTP resources
does not prove remote model computation stopped. The process-wide bridge thread
remains process-owned; this contract does not add per-application thread shutdown.
Builtin SDK request-option forwarding follows `docs/specs/MODEL_GENERATION_OPTIONS.md`.

## Extension voice and availability workers

Model availability, transcription (including the status probe), voice discovery,
injected synchronous speech synthesis and voice control retain their workers through
`run_owned_thread`. A cancelled request or elapsed asyncio deadline waits for the
current worker to settle, including repeated cancellation. Cancellation then
propagates instead of admitting the next capability call or returning its result.
If the worker fails, its exception takes precedence over cancellation; existing
API validation/error mappings still apply. Unhandled worker failures remain visible
to request and container teardown owners. Model generation and default-client
cleanup use this same thread-drain seam.

This owns the awaited synchronous call, not arbitrary tasks or descendants that a
provider detaches. It adds no deadline or forced termination of a stuck thread.
Builtin Piper instead has a directly awaited async path through the application's
native command supervisor. Cancellation and its configured deadline stop the
owned native tree and retain cleanup/capture observations. Its synchronous SDK
entrypoint uses the existing bridge to the same implementation. Native errors
and uncertainty do not become a successful clip or null-backend fallback.
`docs/specs/PIPER_RUNTIME_CONTRACT.md` defines configuration, capture bounds and
the additive API `process_lifetime` observation. The generic null voice backend now
reports unavailable consistently across status, catalog and synthesis.
Injected speech providers remain embedding-owned; there is no new close protocol.
Voice/model identity, configured sample-rate labeling and speech quality remain
separate conformance obligations.

## Evidence boundary and outstanding lifetime work

Task completion and a cooperative resource's successful close are local lifecycle
observations. Generic task cancellation is not a durable effect receipt. Native
command cleanup observations follow `VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`;
the outward journal keeps unresolved dispatch according to its own contract.
Already completed manually registered tasks are outside the close-time failure
collector. Managed background tasks, including the event broadcaster, retain their
unexpected failures when they finish.

The factory owns admitted ASGI invocations and the connector calls they await.
Builtin filesystem connectors now drain their I/O before caller cancellation or
timeout settles, including direct library invocations. API shutdown inherits that
wait for connectors awaited by an owned invocation. Generic extension generation
also drains its model worker and owns builtin client close as specified above.
Direct calls outside an owned
request/background task, unregistered detached tasks, arbitrary blocking threads,
remote effect termination, abrupt host death and durable reconciliation remain
architectural-truth BT-4/BT-5 work. ASGI
task completion alone cannot establish termination of such effects. Cancellation
of the teardown owner itself (including event-loop-wide cancellation) is distinct
from cancelling a close caller: interrupted cleanup must not yield `closed=True`.
No global teardown deadline or forced-stop guarantee for arbitrary registered
resources is added. A resource that never settles can keep close pending; the
five-second fixture cleanup checks are not a general API shutdown SLA.

The scoped tests use real TCP listeners, the public app factory and lifespan,
real detached native command trees dispatched by the authenticated approval route,
live streaming HTTP through Uvicorn, and both real ASGI WebSocket routes through
TestClient. The WebSocket checks are not TCP WebSocket proof. Synthetic owner
failure tests cover observation semantics only. Their exact source/install
versions, outcomes and counterexamples live in the architectural-truth plan.
