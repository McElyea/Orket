# Worker native entry and renewal ownership

Last updated: 2026-09-22
Status: Implementation contract; acceptance remains in the architectural-truth plan

The synchronous Worker adapter requires native owned execution. Event-loop entry
must refuse before HTTP, injected network delay, sleep, random-delay mutation or
renewal-thread creation. Async callers must retain the native invocation through
an owned worker until all admitted work settles.

Each claimed-work invocation owns its renewal thread. Work failure, renewal failure
and caller interruption cannot detach that thread or permit completion before it
settles. Renewal exceptions must reach the invocation caller; they cannot become
an unobserved background exception followed by a completion request. If both work
and renewal fail, preserve the work failure in the exception chain.

The HTTP client is borrowed. Its owner supplies finite request bounds and retains
it until Worker invocations settle, then closes it. Worker cannot terminate an
arbitrary blocked client call; it must retain the admitted call rather than report
cleanup prematurely. No hard termination guarantee for arbitrary Python callbacks
or client implementations is introduced.

The coordinator remains authoritative for claims, lease renewal, hedged completion,
terminal results and publication. Preserve those server semantics, including a
normal renewal refusal and the existing response returned by completion. `run_once`
reports a claimed-work attempt, not independent completion verification. HTTP or
SQLite effects accepted before an error or cancellation are not rolled back.

Acceptance requires refused event-loop entry, actual HTTP and SQLite effects,
renewal-thread cleanup on normal and failed work, visible renewal failure, retained
native work through cancellation/timeout, unchanged lease/hedging regressions, and
installed artifact binding. During held native I/O, an unrelated SQLite operation
must remain below the predeclared 0.5-second bound. This does not establish complete
D2/D3, arbitrary-client termination, model inference, Linux clock repair or lane retirement.
