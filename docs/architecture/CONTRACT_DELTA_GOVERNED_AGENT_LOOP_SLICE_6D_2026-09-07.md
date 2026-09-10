# Contract Delta: Governed Agent Loop Slice 6D

## Summary

- Change title: Durable wake cancellation and evidence-gated recovery controls
- Owner: Orket Core
- Date: 2026-09-07
- Affected contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`

## Delta

- Current behavior: Slice 6C exposes durable manual/API wake admission and
  inspection, while uncertain cancelled or expired claims remain capacity
  barriers with no supported public resolution command.
- Proposed behavior: add authenticated API and CLI wake cancellation, recovery,
  and action inspection backed by atomic SQLite publication of the canonical
  `OperatorActionRecord`, its wake-transition receipt, and the resulting wake.
  Cancellation is
  compare-and-set on the cancellation epoch. Recovery is compare-and-set on the
  fencing generation and requires an explicit `requeue` or
  `confirm_cancelled` resolution, confirmation that the child stopped, cleared
  effect uncertainty, and nonempty evidence references. Rejected state
  transitions retain prior wake truth and publish a conflict or stale receipt.
- Why this break is required now: operators need a truthful way to resolve a
  conservative capacity barrier after external reconciliation. Deleting or
  blindly requeueing the wake would discard uncertainty and could authorize
  duplicate model or effect work.

## Migration Plan

1. Compatibility window: existing agent submit, run cancellation, wake
   admission, and wake inspection commands and routes retain their behavior.
2. Migration steps: use a globally stable action id and current wake epochs;
   reconcile the child and any effect boundary before publishing recovery;
   retain evidence references that support the resolution.
3. Validation gates: prove atomic wake/action publication, exact replay,
   canonical operator-action publication, contradictory-action conflict,
   capacity retention, both recovery
   resolutions, authenticated API access, CLI access, restart persistence, and
   composed run inspection.

## Rollback Plan

1. Rollback trigger: a control can clear uncertainty without evidence, reuse a
   stale epoch, lose its receipt, or permit concurrent replacement work.
2. Rollback steps: remove the public control routes and commands while retaining
   all wake rows and action receipts for inspection.
3. Data/state recovery notes: uncertain wakes continue consuming configured
   capacity after rollback. Do not delete or requeue them without a separately
   admitted reconciliation path.

## Versioning Decision

- Version bump type: patch on the next committed core release step.
- Effective version/date: implementation effective 2026-09-07; no versioned
  commit is created unless separately requested.
- Downstream impact: operators gain durable wake-level cancellation and
  recovery controls through existing operator-action authority. This does not
  broaden run-level operator authority,
  scheduled/webhook ingress, effect capabilities, or provider selection.
