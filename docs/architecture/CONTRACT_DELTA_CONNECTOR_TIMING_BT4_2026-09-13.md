# Contract delta: observed connector timing

## Summary
- Owner: Orket Core, architectural-truth BT-4 / SD-05.
- Date: 2026-09-13.
- Affected contracts: outward connector/API/CLI event payload, supporting runtime
  logging envelope and acceptance schema coverage.
- Durable contract: `docs/specs/CONNECTOR_INVOCATION_TIMING.md`.

## Delta
- Prior behavior: connector invocations reported constant `duration_ms: 0`;
  normalized logging coerced absent timing to zero and truncated fractions.
  A native command sleeping 300 ms independently took 342.4682 ms but reported 0.
- New behavior: injected monotonic measurement carries explicit provenance and
  `awaited_connector_invocation` scope; unavailable is null. Interrupted attempts
  emit supporting telemetry and preserve cancellation/unresolved effect state.
- New runtime log envelopes use v2 for nullable, fractional `duration_ms` and
  optional timing metadata. Acceptance counters distinguish v1 and v2.
- Installed Windows Python 3.11/3.12 exposed `monotonic_ns`'s 15.625 ms clock
  resolution. Default sampling uses monotonic `perf_counter_ns`; the independent
  1 ms overrun bound remains unchanged. Retained provenance still names the
  source that actually supplied each measurement.
- Two unused execution-plan payload helpers that invented zero durations are
  removed; no repository consumers were found.

## Migration Plan
1. Connector consumers must accept the additive `timing` object and nullable
   numeric duration. Logging consumers must recognize v2. There is no new shim.
2. Retain existing ledger schemas, raw history, receipts, sealed witness bytes
   and integrity hashes. Interpret provenance-free connector timing as unavailable
   through the canonical reader. Do not regenerate timing during receipt recovery.
3. Run native slow/failure/timeout/cancel checks, real clock-failure file effects,
   durable receipt republication, mixed logging/reporting, sealed proof gates,
   the canonical source suite and installed Windows/Linux Python 3.11/3.12 gates.

## Rollback Plan
1. Trigger: timing changes outcome, recovery, cancellation or retained integrity.
2. Stop promotion and repair the measurement boundary; do not restore fabricated
   zero or rewrite retained events to fit an older consumer.
3. Existing v1/v2 histories and observed receipts remain original. Unresolved
   dispatch is not retry permission. No data migration or backfill is required.

## Versioning Decision
- Event contract: `invocation_timing.v1`; normalized runtime envelope: `v2`.
- Core release remains uncommitted 0.6.2 worktree development. This checkpoint
  does not create a release, tag or main commit; release policy applies at promotion.
- Effective date: 2026-09-13, scoped worktree implementation.
- Downstream impact: nullable/fractional duration and added provenance. Historical
  v1 coverage retains its meaning; v2 coverage does not assert runtime success.
