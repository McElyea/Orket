# Sandbox creation inputs

## Summary
- Change title: Explicit sandbox creation time at application admission
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-20
- Affected contracts: `Sandbox` construction and `SandboxOrchestrator` creation

## Delta
- Previous behavior: the core `Sandbox` model observed the wall clock when a
  caller omitted `created_at`, after orchestrator preflight had already awaited.
- Current behavior: `Sandbox.created_at` is required. The orchestrator observes
  `RuntimeInputService.utc_now_iso()` when the async creation body starts, before
  its first await, and passes that value through construction and allocation
  publication. Explicit values retain their exact string representation.
- The orchestrator accepts an optional `runtime_inputs` port. Its existing later
  `_now()` observations use that port and retain second precision; creation
  retains full precision. These are observations at their existing lifecycle
  boundaries, not a frozen clock for the whole sandbox lifetime.
- A creation-clock failure reaches neither preflight nor port allocation.
  Existing lease monotonicity checks and Docker/process deadlines stay intact.
- This removes an ambient core effect. Other lifecycle service clocks,
  constructor effects, schema identities and broader D obligations remain open.

## Migration Plan
1. No implicit core timestamp compatibility window. Direct callers provide
   `created_at`; application callers may use the existing runtime input service.
2. Stored sandboxes already containing timestamps require no rewrite. Missing
   values fail validation rather than acquiring a new historical timestamp.
3. Validate explicit-value parity, pre-await capture, clock failure, the affected
   sandbox regressions, and real Docker/SQLite creation and same-path teardown.
   Controlled responses do not establish Docker or provider acceptance.

## Rollback Plan
1. Roll back if explicit capture changes durable sandbox authority or leaks owned
   resources. Retain failure evidence and independently inspect exact-project
   containers, networks and volumes.
2. Revert the scoped implementation/caller changes together with this contract
   and authority update; do not fabricate or rewrite stored creation timestamps.
3. No storage schema migration or cleanup deadline change is introduced.

## Versioning Decision
- Version bump type: patch, scoped remediation checkpoint with a breaking
  construction contract explicitly recorded in the changelog.
- Effective version/date: 0.6.44 / 2026-09-20.
- Downstream impact: direct `Sandbox` constructors must supply `created_at`.
  Existing orchestrator callers need no new argument.
