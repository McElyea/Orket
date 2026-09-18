# SDK memory application ownership and SQLite admission

## Summary
- Change title: Capture SDK memory requests and admit contended SQLite WAL connections.
- Owner: Orket Core.
- Date: 2026-09-18.
- Affected contracts: SDK memory scope selection, controls, profile policy, request publication and shared SQLite WAL connection admission.

## Delta
- Current behavior: An adapter-classified capability provider imports application policy and storage coordination. The frozen SDK request retains mutable nested metadata; caller changes after bridge admission can alter persisted rows.
- Proposed behavior: `orket.application.services.sdk_memory_provider.SQLiteMemoryCapabilityProvider` owns that coordination. Its synchronous `write` entry captures the request before submitting the coroutine to the existing bridge. Each invocation evaluates the existing controls and delegates policy/storage to their existing authorities.
- Why this change is required now: Two real bridge/SQLite controls on unchanged 0.6.13 persist caller mutations during a held storage await. Two unchanged-input controls already pass. The relocation removes three forbidden adapter-to-application pairs without an exception.

Concurrent cold-database probes also exposed WAL admission contention in the
existing shared connection adapter. `connect_sqlite_wal` now verifies the current
mode before attempting a transition. It retries only native `SQLITE_BUSY`-family
errors during admission, closing each failed connection first, within a five-second
monotonic budget with waits capped at 10ms. Each bootstrap connection uses native
timeout zero so the adapter owns that admission wait; admitted connections retain
the existing 5,000ms SQLite busy timeout. Exhaustion raises the last native busy
error. Other error families and non-WAL results still reject. Caller statements,
commits and errors after yield are never retried. This is a bounded admission
policy, not a guaranteed latency or successful admission under a retained lock.

The underlying behavior follows SQLite's documented
[persistent WAL mode](https://www.sqlite.org/wal.html),
[busy-handler limits](https://www.sqlite.org/c3ref/busy_handler.html) and
[primary/extended result codes](https://www.sqlite.org/rescode.html).

## Migration Plan
1. Compatibility window: Migrate the internal provider import from `orket.capabilities.sdk_memory_provider` to `orket.application.services.sdk_memory_provider`. No forwarding shim is added.
2. Migration steps: Workload capability composition and direct internal consumers import the application owner. SDK request/response types, registry capabilities, database paths, extension namespaces and policy codes retain their contracts. Controls remain evaluated for each invocation; this is not a constructor-time toggle snapshot.
3. Validation gates: Actual bridge/SQLite mutation controls, concurrent independent extension scopes, memory policy/toggle regressions and native extension capability allow/deny paths. WAL admission additionally requires retained-lock exhaustion, cancellation/connection-thread teardown, non-busy refusal, unsupported journal-mode refusal and proof that caller errors are not replayed. Fresh source/package/native proof and separately opted-in integration/provider regressions remain required and are recorded in the canonical remediation plan.

## Rollback Plan
1. Rollback trigger: Scope isolation, policy refusal or stored/returned value parity cannot be preserved.
2. Rollback steps: Revert the owner move and consumers together; retain failed proof and settle active calls before replacing code.
3. Data/state recovery notes: No schema migration or historical row rewrite is introduced. Capturing one request does not serialize competing updates to the same profile key, atomically combine policy observation/write/readback, or repair previously borrowed metadata.

## Versioning Decision
- Version bump type: Patch checkpoint destined for main with a matching local annotated tag after verification.
- Effective version/date: 0.6.14 local checkpoint, 2026-09-18.
- Downstream impact: Internal import migration. The shared bridge, lower store initialization/read/write lifetime, native SQLite time defaults and memory-synthesis clocks remain separate C/D work. Direct private/store APIs gain no new snapshot guarantee. No OS containment, whole-memory determinism, shutdown or broad concurrency acceptance is claimed.
