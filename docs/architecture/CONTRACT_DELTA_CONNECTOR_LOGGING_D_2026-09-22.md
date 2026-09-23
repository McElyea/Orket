# Interrupted connector telemetry ownership

## Summary
- Change title: Retain supporting native log publication outside the event loop.
- Owner: Orket Core.
- Date: 2026-09-22.
- Affected contract: `docs/specs/CONNECTOR_INVOCATION_TIMING.md`.

## Delta
- Current behavior: Directory preparation blocks the loop; optional queued log
  writes may outlive the interrupted caller. The latter is permitted by the old
  supporting-telemetry contract, not a violated durable-delivery promise.
- Proposed behavior: Capture the invocation logging root and event inputs; use the
  existing native owner for one complete supporting publication attempt. Repeated
  cancellation retains that work and preserves the original connector exception.
  Expected logging failures remain diagnosed supporting failures. If the diagnostic
  sink also fails, a non-secret exception note preserves the original outcome and
  identifies both failure types. Timing fields
  retain their existing invocation scope, excluding subsequent publication.
- Why now: Source and exact installed .96 controls reproduce loop-thread directory
  work and show the boundary needed for stronger native ownership. Healthy control
  passes. Other logging callers, queues and broader D3 remain separate work.

## Migration Plan
1. Compatibility window: No new compatibility shim or delivery fallback.
2. Migration steps: Public connector signatures remain unchanged. Callers retain
   interrupted invocation tasks through supporting publication. Blocking sinks may
   delay finalization; a native thread cannot be force-stopped safely.
3. Validation gates: Actual HTTP/files/SQLite, repeated cancellation, timeout,
   original-error identity, failed telemetry and captured roots; retained timing
   and uncertainty/API controls; source/installed matrices and authority checks.

## Rollback Plan
1. Trigger: Changed primary outcome, timing schema or effect/recovery authority.
2. Steps: Revert this scoped publication change while preserving retained events.
3. State recovery: Supporting logs are not effect authority. Preserve unresolved
   dispatch and receipts; no log retry grants permission to repeat an effect.

## Versioning Decision
- Version bump type: Pre-1.0 patch with explicit delivery-lifetime change.
- Effective version/date: 0.6.97 / 2026-09-22, subject to scoped acceptance.
- Downstream impact: Interrupted connector calls wait for the native log attempt;
  this is not a universal logging or durable-delivery guarantee.
