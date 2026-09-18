# Scheduler publication clock input

## Summary
- Change title: Carry the pipeline's control-plane clock through scheduler publication.
- Owner: Orket Core.
- Date: 2026-09-17.
- Affected contracts: Orchestrator composition, scheduler namespace publication and activation-failure cleanup.

## Delta
- Current behavior: `Orchestrator(control_plane_clock=...)` supplies issue dispatch, while the scheduler and its activation-failure cleanup read wall time independently.
- Proposed behavior: Scheduler construction accepts `now_utc`; the orchestrator supplies its control-plane clock to both services. Scheduler admission, closeout and activation-failure cleanup use that supplied clock. Direct scheduler construction keeps the existing UTC adapter default. Helpers receive explicit time or the clock they must observe after failure.
- Why this change is required now: A retained Linux scheduler closeout reversed from `2026-09-18T02:53:30.537287+00:00` to `2026-09-18T02:53:21.228116+00:00`. Two controlled pipeline tests supplied a 2041 clock but observed wall time in both transition and child-creation records, independently reproducing the missing wiring.

## Migration Plan
1. Compatibility window: Existing public constructor calls retain their UTC default. No forwarding shim is added.
2. Migration steps: Pass the pipeline/orchestrator clock into the scheduler; supply it explicitly to activation cleanup. Normal engine-boundary fixtures use ordered inputs and close their engine.
3. Validation gates: Real SQLite transition/child publication, controlled promotion failure, exact retained reversal rejection, affected orchestration regressions, fresh package/native proof and provider regressions. The canonical plan records completed proof and outstanding failures.

## Rollback Plan
1. Rollback trigger: Publication or cleanup cannot preserve existing lifecycle behavior with explicit inputs.
2. Rollback steps: Revert the wiring, helper signature and callers together; retain all evidence.
3. Data/state recovery notes: No schema or stored timestamp migration. Reversed timestamps still fail; no clamping, retry or synthetic release is introduced.

## Versioning Decision
- Version bump type: Included in the local 0.6.12 patch checkpoint.
- Effective version/date: 0.6.12 local checkpoint, 2026-09-17.
- Downstream impact: Internal activation-helper callers must supply the cleanup clock. This does not establish monotonic host time or fix native deadline capacity. Scheduler closeout remains a sequence of publications, without the atomic terminal transaction used by issue dispatch; reversed closeout can leave partial publication and active resource authority. No atomicity or automatic repair is claimed.
