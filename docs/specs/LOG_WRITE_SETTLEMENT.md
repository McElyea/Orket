# Optional log-write settlement

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
Lifecycle preparation and migration of other required producers remain separate.

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
Relative workspaces bind through the existing file-root capture; drive-relative
paths refuse. Missing-workspace policy and timezone are selected at call entry.
The timestamp is sampled natively in that selected timezone. This does not claim
that the remaining relative-root cwd observation or lazy writer startup is
nonblocking; canonical lifecycle preparation is still required for complete D3.

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

The tool-gate audit invokes this boundary in `finally`, after its async collection
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
