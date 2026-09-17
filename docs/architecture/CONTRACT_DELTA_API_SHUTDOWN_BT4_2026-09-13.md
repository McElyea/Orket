# API shutdown ownership contract delta

## Summary
- Change title: Shared API teardown with truthful completion state.
- Owner: Orket Core, architectural-truth BT-4.
- Date: 2026-09-13.
- Affected contract(s): `docs/specs/API_RUNTIME_LIFECYCLE.md`,
  `docs/API_FRONTEND_CONTRACT.md`, `CURRENT_AUTHORITY.md`, `docs/RUNBOOK.md`.

## Delta
- Current behavior: `closed` was set before teardown; cancellation could leave an
  owned resource open while subsequent close callers returned normally.
- Proposed behavior: admission stops at close initiation, all callers await one
  teardown, and `closed` requires successful cleanup. Failure is retained and
  reported to subsequent callers. Explicitly unconfirmed native command cleanup
  cannot become successful API teardown.
- Why this break is required now: real listener probes reproduced incomplete
  cancellation teardown and early concurrent return. The old state claimed more
  than it established.

## Migration Plan
1. Compatibility window: no shim. Existing API predicates now use
   `accepting_work`; `closed` is the completion observation.
2. Migration steps: migrate lifespan broadcaster ownership and all container
   admission predicates together. No durable records or historical seals change.
3. Validation gates: cancellation and concurrent-close TCP probes, detached native
   trees, failure contracts, live Uvicorn HTTP shutdown, existing API isolation and
   governed supervisor tests, installed Windows/Linux Python 3.11/3.12 proof.

## Rollback Plan
1. Rollback trigger: regression in app admission, owner teardown or isolation.
2. Rollback steps: revert this scoped lifecycle change and its authority updates;
   reopen the known cancellation gap explicitly. Do not label early return proof
   of successful cleanup.
3. Data/state recovery notes: no stored-data migration. Local close does not
   resolve uncertain durable dispatch or authorize replay of an effect.

## Versioning Decision
- Version bump type: patch when this work is committed for release under the
  core versioning policy; no release or tag is created by this checkpoint.
- Effective version/date: worktree candidate, 2026-09-13.
- Downstream impact: admission checks use `accepting_work`, failed close remains
  failed on reentry, and caller cancellation can wait for resource-owned cleanup.
  General resource deadlines, untracked requests and host-death recovery remain
  open; this delta does not close the whole BT-4 gate.
