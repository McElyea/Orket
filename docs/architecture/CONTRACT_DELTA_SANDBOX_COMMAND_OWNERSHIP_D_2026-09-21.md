# Sandbox command ownership

## Summary
- Change title: Application-owned sandbox command lifetime and process inputs
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-21
- Affected contracts: storage `CommandRunner`, standard `SandboxOrchestrator`
  composition and native command cancellation observations

## Delta
- Previous behavior: async commands inherited invocation-time process inputs,
  had no native deadline and could leave descendants after cancellation or a
  returning leader. Synchronous commands used a separate subprocess path.
- The application factory selects the existing command supervisor, a 300-second
  finite default and captured full environment/current-directory inputs. This
  budget bounds formerly unbounded commands; embeddings can select a different
  positive finite budget by injecting a factory-created runner. The ten-second
  synchronous log override remains unchanged. Existing supervisor cleanup,
  transport deadlines and four-MiB capture limit remain authoritative.
- The adapter requires an explicit owner port, absolute cwd, environment and
  budget. It does not import application authority, choose another backend or
  fall back to direct-child ownership. The standard Windows Job/Linux subreaper
  receipt must confirm cleanup and capture before a completed exit is returned.
  Confirmed nonzero exits remain nonzero results for existing caller policy.
- `CommandResult.lifetime` carries the actual native receipt for standard runs.
  Its default `None` preserves three-field custom results, without conferring
  process proof on custom runners. Lifetime is excluded from repr/equality.
- A confirmed native timeout raises `SandboxCommandTimeout`, preserving the
  `subprocess.TimeoutExpired` category and selected budget. All other incomplete
  results, including launch refusal, raise `SandboxCommandUncertain`, a
  `subprocess.SubprocessError` with the actual lifetime. Error text excludes
  argv, environment and captured output. Existing creation handling marks these
  outcomes for reconciliation rather than inventing a startup-failure receipt.
- Cancellation reaches the caller only after the selected owner settles. The
  adapter raises standard `asyncio.CancelledError`, retaining the owner's
  exception as its cause, so Python 3.11 `asyncio.timeout()` still translates it.
  `sandbox_command_interrupted` publishes the existing `owned_command.v1`
  fields. Native CLI cleanup does not prove daemon resources absent, roll back
  Docker effects or authorize replay. Existing reconciliation remains required.
- Synchronous calls refuse event-loop threads before launch and use the same
  owner through the guarded bridge. Async output retains UTF-8 decoding; sync
  output retains locale text decoding and universal newline translation.

## Migration Plan
1. Direct `CommandRunner()` construction has no compatibility window. Use
   `create_sandbox_command_runner(workspace_root, ...)` or explicitly supply
   the existing core owner port and complete process inputs to the adapter.
2. Standard orchestrator `environment` now supplies the entire child environment
   as well as configuration. Embeddings previously passing partial configuration
   must explicitly compose their full desired environment before construction.
   No ambient keys are merged later. Reconstruct to rotate environment/cwd.
3. Custom runner injection remains supported and retains its own semantics.
   A custom runner's completion is not proof of standard OS ownership.
4. Validate real trees, repeated interruption, external/native deadlines,
   launch/capture refusal, independent SQLite responsiveness, captured inputs,
   sync compatibility, actual Docker lifecycle/recovery and same-path teardown.
   Source/installed proof and Linux availability belong to the canonical plan;
   this contract is not an acceptance record.

## Rollback Plan
1. Retain failures and exact owned process/resource identities if cleanup,
   reconciliation or successful command semantics regress.
2. Revert composition, adapter, callers and authority together. Do not fabricate
   completion for unresolved Docker state or discard its lifecycle records.
3. No database schema migration or replay permission is introduced. This is
   trusted native-command ownership, not hostile-code containment or CAP-2.

## Versioning Decision
- Version bump type: patch scoped remediation with explicit construction/input
  contract breaks; whole-lane acceptance remains pending.
- Effective version/date: 0.6.73 / 2026-09-21; scoped proof belongs to the
  canonical plan and does not establish whole-lane acceptance.
- Downstream impact: direct runner construction, complete environment capture,
  finite default budget and launch-refusal exception category as described above.
