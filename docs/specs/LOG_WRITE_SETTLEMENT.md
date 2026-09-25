# Optional log-write settlement

Owner: Orket Core. Implementation: `orket/logging.py`.

## Authority and admission

Optional async log appends retain the existing bounded queue and single daemon.
Ordinary records use nonblocking admission; a full queue drops the record and
increments `dropped_log_entry_count()`. `ORKET_LOG_QUEUE_MAX` keeps its existing
meaning and default. Event fields remain owned by
`docs/architecture/event_taxonomy.md`.

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

An optional append `OSError` retains its existing best-effort behavior: the daemon
continues and a later marker can settle even though the record was not delivered.
Settlement establishes neither durable delivery nor effect/recovery authority.

Unexpected daemon termination is retained by the existing daemon supervisor.
A frontier waiting for admission or acknowledgement refuses with
`E_LOG_WRITER_TERMINATED`, retaining the recorded failure as its exception cause.
Thread-start `RuntimeError` uses that refusal too; process interrupts retain their
original type. A subsequent frontier cannot replace the retained writer handle.
Ordinary optional logging after daemon death retains bounded enqueue/drop behavior;
it does not gain a delivery guarantee or automatically restart the writer.

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
