# Contract Delta: Governed Agent Loop Slice 6F

## Summary

- Change title: Durable scheduled-wake evaluation and ingress
- Owner: Orket Core
- Date: 2026-09-07
- Affected contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`

## Delta

- Current behavior: Slice 6A-6E admits manual, API, and recovery wakes, but no
  supported path interprets a schedule timezone, missed occurrence, or
  coalescing window.
- Proposed behavior: add authenticated scheduled-wake evaluation backed by one
  durable evaluation receipt and the existing wake queue. Each request carries
  a stable evaluation id, IANA timezone, explicit local occurrence and DST fold,
  UTC observation time, bounded misfire grace, `skip` or `fire_once` missed
  policy, and the fixed `latest` coalescing policy. The evaluation receipt and
  selected wake are published atomically. Exact evaluation replay is
  idempotent; contradictory identity reuse conflicts without changing prior
  truth. Scheduled wakes retain their schedule trigger metadata for inspection.
- Why this break is required now: inferring timezone, DST, missed-trigger, or
  coalescing behavior inside the supervisor would make restarts and duplicate
  scheduler delivery ambiguous. Durable evaluation must precede dispatch.

## Migration Plan

1. Compatibility window: manual/API/recovery wake routes, commands, queue
   records, and supervisor behavior retain their existing contracts.
2. Migration steps: scheduler callers submit non-overlapping evaluation windows
   with stable evaluation ids and fully materialized dispatch envelopes for each
   due occurrence. Local timestamps use an IANA timezone and canonical DST fold.
3. Validation gates: prove UTC conversion across DST folds, nonexistent-time
   rejection, missed `skip`, missed `fire_once`, latest-only coalescing, atomic
   receipt/wake publication, exact replay, contradictory replay, authenticated
   API access, restart persistence, and supervisor consumption.

## Rollback Plan

1. Rollback trigger: an evaluation can enqueue an unintended occurrence, lose
   its receipt, reinterpret DST on replay, or produce two selected wakes.
2. Rollback steps: remove the scheduled evaluation routes and composition while
   retaining all schedule receipts and already admitted wakes for inspection.
3. Data/state recovery notes: do not delete admitted scheduled wakes. Cancel or
   reconcile them through the existing wake-control contract.

## Versioning Decision

- Version bump type: patch on the next committed core release step.
- Effective version/date: implementation effective 2026-09-07; no versioned
  commit is created unless separately requested.
- Downstream impact: scheduler integrations gain one authenticated durable
  ingress contract. Webhook ingress remains outside this delta and is
  subsequently admitted by Slice 6G; generalized wake-driven effects remain
  open.
