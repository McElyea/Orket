# Optional log-write settlement

Status: Active
Last updated: 2026-09-28

Owner: Orket Core. Public facade: `orket/logging.py`. The single process-global
queue, writer, failure, drop, directory and subscriber state lives in
`orket/adapters/observability/log_publication.py`.

The v0.6.106 internal extraction preserves existing public functions and native
stage bodies. Private observation seams belong to that owner; there are no
forwarding state aliases in the facade. This extraction does not itself repair
optional caller-loop work, capture inputs, prepare logging or drain API handoffs.
The subsequent API registration drain shares this owner and its condition but
has a separate cutoff and acknowledgement protocol; it does not expand the
append frontier. See `docs/architecture/CONTRACT_DELTA_API_LOG_HANDOFF_D_2026-09-25.md`.

The subsequent optional-publication correction captures built-in event inputs
before admission and moves native processing onto this same writer. Its scope
and migration are in
`docs/architecture/CONTRACT_DELTA_OPTIONAL_LOG_PUBLICATION_D_2026-09-27.md`.
Explicit lifecycle preparation now uses that same owner as specified below;
migration of the other required producers remains separate.

## Authority and admission

Optional async log appends retain the existing bounded queue and single daemon.
Ordinary records use nonblocking admission; a full queue drops the record and
increments `dropped_log_entry_count()`. `ORKET_LOG_QUEUE_MAX` keeps its existing
meaning and default. Event fields remain owned by
`docs/architecture/event_taxonomy.md`.

Event-loop `log_event` detaches exact built-in payload and option graphs with the
shared `capture_log_event_inputs` authority. Event names and explicit roles must
be exact strings; workspaces must be `None` or an exact platform-native `Path`.
Custom values, cycles, non-string mapping keys and non-finite scalars refuse with
`E_LOG_EVENT_INPUT_UNSUPPORTED` before subscriber capture or queue effects.
Relative workspaces combine lexically with the prepared invocation root;
drive-relative paths refuse. Missing-workspace policy and timezone come from the
prepared application selection. The timestamp is sampled natively in that selected
timezone. Optional call entry does not observe cwd or start a writer.

## Explicit preparation and application binding

`LoggingInputs` owns the absolute invocation root, timezone, missing-workspace
mode and positive queue capacity. Select those values from an application's
captured environment. Direct async embeddings await
`orket.logging.prepare_logging(inputs)` before entering
`orket.logging.bind_logging(prepared)` around their actual operation. Native
embeddings may use `prepare_logging_native`; that entry refuses loop-thread use.
Binding performs no I/O. Loop publication without a prepared binding refuses
with `E_LOGGING_PREPARATION_REQUIRED` before subscriber capture or queue effects.
Native direct publication remains synchronous and observes native inputs when
unbound; it does not require optional queue admission.

Preparation configures the existing empty process-global queue and attempts its
single daemon start natively under the shared I/O owner. Repeated interruption
retains that attempt. Success after interruption leaves the process owner usable
by a later preparation but propagates the caller's cancellation. Native failure
has precedence. The first selected capacity remains fixed; another capacity
refuses with `E_LOGGING_QUEUE_CONFIGURATION_CONFLICT`. Existing invalid environment
capacity values still select the existing default.

The thread handle is retained before its start attempt. Start failure latches its
first cause; later preparation cannot replace or retry that handle. RuntimeError
retains the existing writer-termination envelope; other failures retain their
original type. A partially started daemon can remain alive until process exit.
Thread allocation before a handle exists is outside that start-failure latch.
No application-local stop, join, restart or forced-termination protocol is added.

Canonical API, CLI, engine/pipeline, driver, organization and webhook composition
prepare their selections and bind admitted operations and cleanup. Borrowed engine,
pipeline, API and webhook lifetime yields carry no binding token to another task.
CLI command setup enters and exits its application context in the same task.
The Gitea reconciliation and worker-coordinator CLIs select logging from
their captured process root and environment before adapter admission. They bind
the adapter's construction, operation and cleanup in the invocation task. State
conflicts remain reportable and lease refusal remains a skip; explicit
missing-workspace refusal and existing CLI exit/report semantics are retained.
API/webhook request admission binds the selected application until the inherited
owner settles the request; a subsequent refused ASGI send sees the restored caller.
The native frontier retains cold preparation and its original marker semantics.
Previously prepared optional calls retain bounded enqueue/drop behavior after
writer death; preparation itself refuses a failed writer. Required producers
and their input/context obligations remain separately inventoried. Command and
fixture lifetime finalizers use the shared finalizer policy after actual resource
cleanup: later caller interruption does not replace the selected outcome, while
native publication failure remains subject to each caller's original failure
mapping. They retain fatal failures until the public caller observes them. They
are required native attempts, outside the optional queue frontier. Contract:
`docs/architecture/CONTRACT_DELTA_REQUIRED_FINALIZERS_D_2026-09-28.md`.
Migration and proof limits:
`docs/architecture/CONTRACT_DELTA_LOGGING_PREPARATION_D_2026-09-28.md`.

## Required producer inputs

Dual-ledger factory composition forwards its selected absolute workspace to
`AsyncDualModeLedgerRepository`; direct constructors must supply `workspace_root`.
Default telemetry captures exact built-in event values before native admission
and retains that invocation's workspace for its supporting error event. Custom
sinks keep their borrowed payload/callback and returned-awaitable contracts.
Existing counted failure and fallback-handler policy remains authoritative;
telemetry does not authorize ledger completion or reverse durable effects.

Webhook required events select the handler's current workspace and capture exact
built-in name/payload values before their existing native worker is admitted.
Each later event selects anew. Unsupported values refuse at this boundary;
earlier delivery deduplication can remain committed. The ASGI parser can accept
non-finite JSON values: if projected into a required event they trigger the
existing uncaught-publication failure response (500), before dispatch. This
does not introduce a whole-payload HTTP validation policy.

Prepared contexts continue to select environment and timezone; native timestamps
are still sampled during publication. Unbound direct native publication retains
its existing input fallback. These producer changes add no writer shutdown,
whole-request atomicity or general required-producer closure. Migration and proof:
`docs/architecture/CONTRACT_DELTA_LEDGER_WEBHOOK_EVENT_INPUTS_D_2026-09-28.md`.

The SDK runner's required lifetime observation captures its event inputs before
native admission. Native publication failure, including cancellation/fatal
outcomes, retains typed uncertainty and the unadopted exchange. Caller-only
interruption keeps its existing cancellation policy. The supporting uncertainty
event keeps its exact secondary-error protocol. Result/effect authority and
migration belong to `docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md`; this adds no
optional queue or process-exit settlement guarantee.

## Optional publication stages

The event-specific wrapper delegates its graph walk to the single pure
`core/contracts/value_capture.py` owner and supplies its unchanged stable error
code. This extraction adds fixture admission as another caller without changing
logging's root/event checks, admitted types, capture behavior or publication policy.
This shared capture extraction is active for prospective checkpoint 0.6.113.
Its copied-source and current-source event/fixture controls and pending installed
acceptance are recorded in
`../architecture/CONTRACT_DELTA_FIXTURE_INPUT_TIME_D_2026-09-27.md`; it adds no broader
logging-preparation claim.

Main and applicable runtime-artifact attempts occupy independent bounded slots.
A dropped main suppresses its handler and subscriber attempts; an independently
accepted artifact can still append. A dropped artifact does not suppress an
accepted main's subscriber attempts. The main's handler, directory preparation,
serialization and write execute natively, followed by any admitted artifact and
subscriber attempts. Uninvoked delivery tokens settle on drop or writer failure.
API handoffs retain their separate later acknowledgement and registration drain.

Optional admission increments the same per-path drop counter. Sparse overflow
warnings execute on the writer, using one bounded pending warning slot. Multiple
sparse warning thresholds reached while it is held coalesce to the latest pending
threshold/path; the total drop count remains exact. A dead writer cannot deliver
these warnings. The lower-level append interface keeps its existing semantics.

`settle_log_write_frontier()` is a synchronous native-context boundary. It starts
the same daemon when necessary, inserts one marker into the existing queue and
waits until that marker is acknowledged. Calling it from a running event loop
refuses before writer start or marker admission with
`E_LOG_WRITE_FRONTIER_REQUIRES_NATIVE_CONTEXT`.

The cutoff is successful marker admission, not function entry. A full queue makes
the native caller wait for a slot. The marker is never dropped and does not itself
increment the ordinary-record drop counter. It occupies one bounded queue slot;
concurrent ordinary records can therefore drop while that slot is occupied.
There is no priority or fairness guarantee for competing admissions.

## Settlement and failure

Acknowledgement means that every optional append accepted before the marker has
finished its append attempt. Records admitted after the marker are excluded even
if their appends are already running when the caller resumes. Native direct writes,
subscriber callbacks and other producers are outside this queue frontier.
Earlier optional publication stages can delay the marker, but it grants no
subscriber delivery or API handoff acknowledgement claim.

An optional append `OSError` retains its existing best-effort behavior: the daemon
continues and a later marker can settle even though the record was not delivered.
This includes the `logging_subscriber_failed` diagnostic append: a refused optional
diagnostic write cannot skip later subscriber attempts or strand their tokens.
Its timestamp/materialization and standard-handler failures remain fatal; only
the optional append has `OSError` best effort. Native required diagnostic appends
continue to propagate their write failures to the retained caller.
Settlement establishes neither durable delivery nor effect/recovery authority.

Unexpected daemon termination is retained by the existing daemon supervisor.
A frontier waiting for admission or acknowledgement refuses with
`E_LOG_WRITER_TERMINATED`, retaining the recorded failure as its exception cause.
Thread-start `RuntimeError` uses that refusal too; process interrupts retain their
original type. A subsequent frontier cannot replace the retained writer handle.
Ordinary optional logging after daemon death retains bounded enqueue/drop behavior;
it does not gain a delivery guarantee or automatically restart the writer.
Those post-death optional calls issue no registration tokens. Non-`OSError`
failures in deferred stages still terminate the writer and retain their original
cause; they are not converted to a successful frontier or a late-warning counter.
Handler and main-directory preparation failures, including `OSError`, are fatal
too; best-effort `OSError` handling belongs to the admitted append attempts.
Required/native publication still runs inline and propagates its main-write
failure to its retained caller.

A live held append keeps the native waiter pending. This boundary adds no forced
thread termination, settlement deadline, retry, application shutdown or global
writer-stop operation. Async ownership, preparation and input capture remain
separate contracts.

## Audit ownership

The tool-gate audit prepares and binds native logging before entering its async
collection. That preparation can fail before collection starts; no cold-start
ordering parity is promised. Its direct dispatch harnesses receive the selected
prepared value. The same invocation retains the frontier in `finally`, including
preparation failure. The tool-gate audit invokes this boundary after its async collection
owner returns or raises and before its temporary workspace owner exits. Audit
publication follows successful collection, settlement and workspace cleanup.
Collection or cleanup failure cannot publish a new audit result. When this audit
invocation has a collection or required-close exception and settlement raises the
exact built-in `RuntimeError(LOG_WRITER_TERMINATED_ERROR)`, the original exception
continues with its identity, traceback, cause, context and prior notes preserved
as they entered settlement. One note adds the stable writer-termination code,
secondary type and daemon-cause type. It contains no exception message or payload
and does not attach the secondary exception object. The existing logging owner
retains the daemon failure independently.

A caller's handled exception is not this invocation's primary. Successful
collection followed by writer termination raises the settlement error and cannot
publish. Unknown settlement errors, same-text subclasses, different argument
tuples and settlement interrupts retain normal `finally` precedence. A primary
interrupt remains outward when the exact known secondary adds its note. Fatal
settlement is a refusal; it does not claim that stranded appends completed.

The architectural-truth remediation plan owns opening/closing observations,
installed acceptance and publication status. This contract is not an acceptance
record. Migration: `docs/architecture/CONTRACT_DELTA_LOG_WRITE_SETTLEMENT_D_2026-09-24.md`.
