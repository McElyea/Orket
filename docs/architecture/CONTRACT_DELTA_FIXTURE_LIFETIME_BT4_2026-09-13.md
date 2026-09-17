# Contract delta: application-owned fixture verification

## Summary
- Owner: architectural-truth BT-4.
- Date: 2026-09-13.
- Affected contracts: `Orchestrator.verify_issue`, legacy synchronous fixture
  entrypoints, persisted `VerificationResult`, native and Docker fixture lifetime.
- Durable authority: `docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`.

## Delta
- Current failure: `verify_issue` abandons a thread running synchronous fixture
  execution. Cancellation returns while the fixture and descendants continue
  writing. Killing the Docker client also cannot establish container teardown.
- Required boundary: `FixtureVerificationService.verify` is the canonical async
  application entrypoint. Native commands use `VerificationProcessSupervisor`;
  container execution has a separately retained identity and confirmed removal.
- Core fixture code owns deterministic policy/result interpretation only. The
  application supplies environment and time, collects filesystem observations,
  owns execution, and applies scenario updates after the observed outcome.
- Existing `FixtureVerifier.verify` and `VerificationEngine.verify` become explicit
  migration errors before any effect. They must not execute, create an event loop,
  or forward through a hidden synchronous-to-async bridge. The existing exported
  symbols remain temporary migration tombstones, tracked below.
- `VerificationResult.process_lifetime` is an additive nullable observation.
  Historical rows remain unchanged. Cancellation does not publish a new fixture
  result or scenario status; uncertainty cannot authorize successful verification.
- Unknown execution modes fail explicitly. The production guard still requires
  container mode unless the operator explicitly allows native execution. Native
  path containment does not establish read-only storage or hostile-code isolation.

## Migration Plan
1. Move the production `verify_issue` caller and repository tests to the async
   service. Reuse one fixture runner and result interpreter for both execution
   modes; do not maintain another functioning synchronous executor.
2. Removal ticket `BT4-FIXTURE-SYNC-RETIRE`: remove the existing synchronous
   migration tombstones and their deprecated exports during the architectural-truth
   0.7.0 compatibility cutover, after caller inventory and contract acceptance.
   Owner: Orket Core; canonical tracking is in the active remediation plan.
3. Docker ownership: retain a fresh name/owner binding before creation, inspect
   the actual immutable container ID and labels, attach to that ID, inspect its
   terminal state, and remove only the bound ID. A failed CLI command is not proof
   of absence. Cleanup requires a successful daemon observation showing absence.
   A lost create response requires discovery against the original name and owner;
   a foreign container is never removed to obtain a clean result.
4. On cancellation stop admission, finish owned command cleanup, remove the owned
   container if present, and propagate cancellation only after the cleanup result.
   Repeated cancellation must not abandon cleanup. Preserve uncertainty when
   the Docker daemon cannot establish teardown.
5. Validate native children/grandchildren and repeated cancellation through the
   public entrypoint, fixture outcome parity, production guard, invalid modes,
   non-starvation, no post-cancellation persistence, installed Windows/Linux
   environments, and explicit live Docker acceptance with teardown in the same
   execution path. Mocked Docker success is contract evidence only.

## Rollback Plan
1. Trigger: incorrect fixture interpretation, unsupported process ownership, or
   unconfirmed Docker cleanup.
2. Disable affected fixture admission while repairing the owner. Do not restore
   abandoned threads, direct-child-only termination, or an unsupervised fallback.
3. Preserve existing verification records and unresolved resource observations.
   Do not fabricate historical cleanup or rewrite old results to match the change.

## Versioning Decision
- Effective in the unreleased architectural-truth worktree; no release/version
  bump is performed by this checkpoint.
- Synchronous execution semantics intentionally break with an explicit migration
  error. The public async issue-verification signature remains unchanged.
- The nullable lifetime field is additive. The 0.7.0 cutover removes tombstones;
  keeping them does not authorize a second executor or a core-to-application import.
