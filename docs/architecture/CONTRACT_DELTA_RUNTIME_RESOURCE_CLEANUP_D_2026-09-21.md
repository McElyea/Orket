# Runtime resource cleanup contract delta

Status: active scoped D implementation; whole-lane acceptance remains open.

Engine, execution-pipeline and runtime-context cleanup retain their declared
resource order and preference for `aclose` over `close`. Each close-capable target
is attempted even when an earlier target fails. Targets without either capability
remain valid. This does not expand the list of resources owned by those runtimes.

The application cleanup supervisor owns the whole admitted sequence. Synchronous
close functions execute in an owned worker; asynchronous functions execute on the
event loop. An awaitable returned by a synchronous function is awaited after the
worker returns. A synchronous close implementation that requires a running event
loop must migrate to `async def close` or `async def aclose`. Worker construction
and native close ports must support their documented thread usage.

Repeated caller cancellation waits for admitted cleanup to settle. Cancellation
does not silently abandon later targets. A target's own cancellation is retained
as a failure while the supervisor attempts later targets. A single failure is
re-raised unchanged; multiple failures are retained in an exception group. Groups
may be nested when an owned runtime closes another runtime. Callers that inspect
cleanup failures must handle exception groups as well as individual exceptions.
Native failure remains visible when caller cancellation also occurs.

Engine/pipeline `_closed` is set only after successful return from required
cleanup. Failed resources are not labelled closed. A later explicit close may
retry them; close-capable ports must retain their existing idempotence obligations.
The runtime context has no new lifecycle flag. This change does not add a timeout,
weaken an existing deadline, guarantee completion of an uncooperative close port,
or serialize simultaneous independent calls to `close`.

Integration proof uses actual runtime construction and real SQLite handles at
supported injected repository ports. A controlled cleanup transaction fails in
SQLite before releasing its connection; later connections must close and the
original failure must remain observable. Additional controlled native ports
exercise the outer engine/pipeline cleanup boundaries. These observations do not
claim that default per-operation SQLite repositories retain persistent handles.

Held native close proof retains the 0.5-second concurrent SQLite response bound,
50ms timeout after admission, 0.8-second release timer and five-second join limit.
Cancellation, timeout and failure are distinct observations. Runtime action and
completion-authority semantics are unchanged. Broader constructor failures before
owner transfer, omitted resource owners, provider success, whole-suite Quality,
Linux clock acceptance and remaining D/E/CAP work remain separate obligations.

Predecessor: `CONTRACT_DELTA_CONFIG_SYNC_BRIDGE_D_2026-09-21.md`.
