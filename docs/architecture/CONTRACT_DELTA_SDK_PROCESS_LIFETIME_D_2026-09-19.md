# SDK subprocess and exchange ownership

## Summary
- Change title: Own admitted SDK process lifetime and preserve unknown outcomes.
- Owner: Orket Core.
- Date: 2026-09-19.
- Affected contracts: `docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md`, SDK execution
  and extension control-plane closeout.

## Delta
- Current behavior: Raw subprocess cancellation can return while its workload
  child remains alive. Temporary exchange workers are unowned. Missing child
  observations can reach generic terminal failure with no observed side effects.
- Proposed behavior: Reuse the native command supervisor and owned file workers;
  retain exchange data and unresolved control-plane state on uncertain execution.
  Adopt only complete, consistent SDK results after confirmed native cleanup.
  Apply the existing controller default of 900 seconds to direct SDK execution,
  with an explicit finite host override, and the shared native 4 MiB capture bound.
- Why now: The installed 0.6.33 cancellation observation under
  `.tmp/c-extension-loading/sdk-lifetime-observation-repaired/` demonstrates the
  live child leak. C/D requires repair without weakening established BT-4 ownership.

## Migration Plan
1. Compatibility window: No unsafe raw-subprocess fallback. Manifest/stdin result
   contracts and valid child errors remain unchanged; cancellation may wait for
   cleanup, and incomplete execution now raises uncertainty instead of terminal truth.
   Confirmed SDK cancellation retains its native cause/event while propagating the
   ordinary cancellation type, preserving controller timeout behavior on 3.11/3.12.
2. Migration steps: Embeddings retain typed uncertainty and its exchange path;
   do not replay an unresolved invocation. Direct long-running hosts explicitly
   select their finite deadline. Unsupported native hosts remain unadmitted.
3. Validation gates: Actual SDK success/error, cancellation and descendant tests;
   file-worker interruption; independent control-plane reads after missing result;
   negative protocol/cleanup controls; source and installed Windows/Linux 3.11/3.12
   regression, package parity and dependency checks. Scoped proof is recorded in the canonical plan.

## Rollback Plan
1. Rollback trigger: Lost child ownership, false terminal truth or admission drift.
2. Rollback steps: Refuse affected SDK execution while repairing the owner; do not
   restore an unowned process path as a fallback.
3. Data/state recovery notes: Preserve unresolved records and exchanges. Process
   cleanup is not proof that external effects did not occur.

## Versioning Decision
- Version bump type: Patch within the active architectural-truth remediation.
- Effective version/date: 0.6.34 / 2026-09-19; scoped local source/installed checkpoint.
- Downstream impact: Bounded native execution, owned cancellation and explicit
  uncertainty; no new hostile-code containment or workload capability admission.
