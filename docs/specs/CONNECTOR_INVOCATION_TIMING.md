# Connector invocation timing

Status: Active contract
Last updated: 2026-09-13
Owner: Orket Core

## Authority and measurement

`orket/core/contracts/invocation_timing.py` defines `InvocationTiming` and its
`invocation_timing.v1` provenance. `OutwardConnectorService` owns the measurement;
`ConnectorInvocationTimer` samples the injected monotonic nanosecond callable.
The default source is `RuntimeInputService.monotonic_ns`, backed by
`time.perf_counter_ns`. This source is monotonic on supported runtimes and is an
observation, not deterministic input. It avoids the coarse `GetTickCount64`
resolution of `time.monotonic_ns` on Windows Python 3.11/3.12.

Every normally returned connector event contains `duration_ms` and `timing`:

| Field | Meaning |
| --- | --- |
| `duration_ms` | Finite nonnegative milliseconds, preserving fractions; null when unavailable. |
| `timing.schema_version` | `invocation_timing.v1`. |
| `timing.status` | `measured` or `unavailable`. |
| `timing.clock` | Default `python.time.perf_counter_ns`; `python.time.monotonic_ns` for retained observations from that clock; `injected_monotonic_ns` for explicit injection; null for legacy unmeasured history. |
| `timing.scope` | `awaited_connector_invocation`. |
| `timing.reason` | Null for measured values; a nonempty reason for unavailable values. |

The interval starts after connector lookup and argument validation, immediately
before the executor timeout scope. It ends after that await returns or raises,
including cleanup the adapter actually awaited. It excludes approval, admission,
pre-dispatch policy work, result projection and durable receipt publication.
It does not establish the lifetime of remote effects or unowned descendants.
Builtin filesystem invocations, including direct calls without a retained outward
authorization binding, keep an owned I/O task through cancellation. The caller
waits for that operation and its worker threads to settle before cancellation
propagates or the deadline scope returns timeout. Repeated caller cancellation
cannot release that ownership early. The measured interval includes this drain.
This does not force-stop a thread, undo a mutation, or establish a hard deadline
for blocked filesystem I/O. A stuck worker keeps the invocation pending.
The built-in command connector now supplies a separate `owned_command.v1`
lifetime observation through the shared application supervisor, defined in
`docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`. Timing includes its awaited
cleanup but cannot substitute for that observation or prove remote effect reversal.

Equal monotonic ticks are a measured zero. Missing, invalid, regressed or failed
samples are unavailable, never invented zero. Reasons are `clock_unavailable`,
`invalid_monotonic_sample` or `invalid_monotonic_interval`. Measurement failure
does not turn a successful effect into failure or authorize retry. Clock
diagnostics name the fault without including connector arguments.

## Outcome and interrupted attempts

Normal success, connector-declared failure and timeout retain their existing
outcome meanings and receive the same timing fields. A timeout does not establish
that no effect occurred. Cancellation is re-raised; unknown execution failures
retain their original exception. Both emit supporting
`outward_connector_interrupted` telemetry with `connector_name`, `args_hash`,
`observation` (`cancelled` or `unresolved`) and the timing fields. Native commands
include `process_lifetime` when observed. They do not
fabricate a returned effect result, `tool_invoked` event or completed receipt.
The durable effect owner retains unresolved dispatch intent.

Supporting log delivery follows the existing bounded logging queue and may be
dropped with queue diagnostics. The event has no session identity, so it is
retained in the workspace log when delivered; it does not create a session
runtime-event artifact by itself. It is not recovery authority.

An observed receipt commits the timing it actually captured. Publication retry
must reuse the complete retained receipt and digest without sampling a new
duration. Timing is covered by event/receipt integrity hashes. It does not govern
authorization, fencing, replay identity or success. Capacity claims require
separately declared workload sampling and resource evidence; this interval alone
cannot establish them. A deterministic decision using timing requires an
explicitly captured input contract.

## Projection and historical data

New normalized logging envelopes use `schema_version: v2`. Their `duration_ms`
is a finite nonnegative number or null. Missing/invalid values stay null and
fractions survive projection. Present connector `timing` metadata is retained.
The raw event payload and existing historical envelopes are not rewritten.
Other event producers do not acquire connector provenance merely by being logged.

Legacy connector payloads lack provenance and include previously fabricated
zeros. `read_invocation_timing` interprets them as unavailable with
`reason: legacy_unmeasured`, leaving the original payload untouched. A numeric
legacy field alone is not measurement evidence. Sealed histories, witness
fixtures and their v1 hashes must never be resealed for this migration.

Acceptance reports retain explicitly historical `runtime_event_schema_v1_count`
and coverage fields, and add corresponding v2 count/coverage fields. Old reports
without v2 counts contribute zero v2 coverage; envelope coverage is not timing
availability or runtime success. Benchmark-generated support rows and unrelated
turn/provider summaries retain their own schemas and need their own timing audit.

## Verification boundary

Contract tests cover clock injection, fractional precision, invalid samples,
unavailable values and unchanged exception identity. Native command integration
checks cover a 300 ms sleep with successful/failed exit, a 200 ms timeout and
cancellation after startup. Independent `perf_counter_ns` observations allow
at most 1 ms of measurement overrun and 50 ms for outer validation/projection
and scheduling; minimum elapsed work must remain visible.

Actual filesystem clock-failure tests verify that timing loss does not change
the effect. SQLite publication-failure recovery verifies receipt reuse. Real
logging/reporting verifies v1 history preservation and v2 null/fraction handling.
These are scoped correctness checks, not throughput, peak memory, arbitrary
remote cancellation or descendant-lifetime proof.

Filesystem ownership delta:
`docs/architecture/CONTRACT_DELTA_CONNECTOR_FILESYSTEM_LIFETIME_BT4_2026-09-13.md`.
