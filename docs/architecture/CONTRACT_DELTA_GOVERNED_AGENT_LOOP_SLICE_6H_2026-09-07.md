# Contract Delta: Governed Agent Loop Slice 6H

## Summary

- Change title: Wake-fenced effect preparation and operator-authorized resume wakes
- Owner: Orket Core
- Date: 2026-09-07
- Affected contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`

## Delta

- Current behavior: a claimed wake can run the bounded agent loop and durably
  pause on `effect_approval_required`, but effect proposals must then be
  prepared, resolved, and resumed by direct application-service calls. The
  existing resume helper changes the run to `executing` before a durable wake
  exists, leaving a crash gap between the claimed transition and later work.
- Proposed behavior: the active wake prepares every accepted proposal through
  the existing issue-scoped effect service before completing. Preparation
  rechecks the wake fence before every authoritative publication and after an
  external observation, so stale workers cannot publish effect truth. Read
  observations and approval-required writes remain the only admitted effect
  capabilities. An authenticated operator resolution, or the explicit
  continuation route for a fully observed read-only proposal set, accepts one
  aggregate checkpoint only after all proposal journals have safe observations,
  records a request-digest-bound resume authorization, and enqueues one
  existing-run wake. The run remains
  `operator_blocked` until that wake is claimed; the claimed wake validates the
  exact authorization and performs the `operator_blocked -> executing`
  transition under its live fence. Exact retries are idempotent. Denial closes
  the run and queues no resume work.
- Why this break is required now: a continuously available supervisor must not
  stop at a durable pause that only an internal test harness can resolve, and
  it must not claim a resumed run before durable executable work exists.

## Migration Plan

1. Compatibility window: proposal, approval, journal, per-write checkpoint,
   queue, and child IPC schemas remain unchanged. Direct resume callers must
   treat `prepare_resume` as authorization only; execution begins only through
   `activate_resume` beneath a claimed wake.
2. Migration steps: submit effects through the existing bounded wake path,
   resolve the pending approval or explicitly continue a safe read-only set
   through the authenticated run endpoints with explicit decision/lease
   timestamps, and allow the configured supervisor to claim the resulting
   deterministic resume wake.
3. Validation gates: prove automatic preparation, no pre-approval mutation,
   stale-worker refusal, approval and denial, aggregate receipt/checkpoint
   coverage, request-bound activation, retry idempotency, restart persistence,
   and public API-to-real-child completion.

## Rollback Plan

1. Rollback trigger: stale wake authority can publish effect state, approval
   resolution can resume without complete safe observations, a denied write
   mutates or queues work, or a run is reported executing before a valid resume
   wake is claimed.
2. Rollback steps: disable the effect-resolution route and wake preparation
   composition while retaining durable approvals, journals, checkpoints,
   operator actions, and wakes for inspection/recovery.
3. Data/state recovery notes: do not delete partial effect authority. Resolve
   pending gates or recover claimed wakes through existing evidence-gated
   controls; uncertain effects require observation/reconciliation.

## Versioning Decision

- Version bump type: patch on the next committed core release step.
- Effective version/date: implementation effective 2026-09-07; no versioned
  commit is created unless separately requested.
- Downstream impact: operator clients gain one effect-resolution endpoint and
  must supply explicit bounded resume timing inputs on approval.
