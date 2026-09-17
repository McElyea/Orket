# Bug-fix phase values and application effects

## Summary
- Owner: Orket Core.
- Date: 2026-09-16.
- Contracts: `docs/ARCHITECTURE.md`, `docs/architecture/event_taxonomy.md`.

## Delta
- Core `BugFixPhase` requires `started_at`; extension and expiry require explicit
  `now`. The initial end derives from that same start value. Duration caps,
  thresholds, persisted field names and phase-two identifiers stay unchanged.
  Status uses Python's `StrEnum`: string conversion returns the status token;
  serialized status tokens remain unchanged.
- `BugFixPhaseManager` moves to `orket.application.services.bug_fix_phase_manager`.
  Its constructor requires `workspace` and `now_utc`. ExecutionPipeline supplies
  its workspace and runtime-input clock, including child pipeline composition.
- Application owns the active cache, persistence and events. Candidate updates
  are copied; a configured store must save and read back the same value before
  cache publication and the corresponding event. Failed or mismatched persistence
  propagates without a success event or candidate cache update. `db=None` remains
  explicitly in-memory ownership; its events do not establish durable persistence.
- One manager serializes transitions. Waiting for ownership remains cancellable;
  admitted persistence and synchronous event output remain owned until settled,
  including cancellation and timeout. Logging runs in the existing owned worker.
- Existing legacy domain module aliases use explicit module imports. Their module
  identities stay unchanged. The application manager is no longer exported from
  either core or the deprecated domain package; no reverse dependency shim exists.

## Migration Plan
1. Import the manager from application and supply its clock and workspace.
2. Direct model constructors supply start time; callers of `extend_phase` and
   `is_expired` supply `now`. Previously saved phase JSON already contains start.
3. Preserve serialized phase values. Do not manufacture missing historical time.
4. Require core parity, real SQLite lifecycle/reopen and write-refusal controls,
   pipeline clock/workspace proof, owned cancellation/timeout, affected installed
   Windows/Linux Python 3.11/3.12 regressions, and the dependency observation.

## Limits and Rollback Plan
- The per-manager lock and read-back are not a cross-process compare-and-swap or
  transaction coupling SQLite to event files. A failed read-back after a committed
  write may leave durable state changed; the exception does not claim rollback.
- Events retain their existing payloads and observability timestamps. This does
  not repair the shared logger's subscriber or secondary-artifact guarantees.
- Stop acceptance on parity, ownership, packaging or claim-before-effect failure;
  repair the application seam while retaining old evidence and explicit inputs.
- Other core ambient inputs, hidden state and async paths remain C/D obligations.

## Versioning Decision
- Development-candidate internal API move; no release or version bump yet.
- No persisted schema migration or new compatibility API. Current proof and
  acceptance disposition remain in the canonical architectural-truth plan.
