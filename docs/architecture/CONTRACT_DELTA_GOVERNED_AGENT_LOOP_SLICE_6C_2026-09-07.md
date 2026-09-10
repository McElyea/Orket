# Contract Delta: Governed Agent Loop Slice 6C

## Summary

- Change title: Public durable manual-wake CLI transport
- Owner: Orket Core
- Date: 2026-09-07
- Affected contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`

## Delta

- Current behavior: Slice 6B admits authenticated API wake persistence and
  opt-in API-owned dispatch, but an operator cannot place a manual wake on that
  queue through a supported public command.
- Proposed behavior: add `orket agent wake enqueue`, `list`, and `inspect` as a
  public manual transport. API and manual ingress share one application-owned
  validation and persistence service, while source-scoped identities prevent
  equal occurrence ids from colliding across transports. The CLI only persists
  work; it does not start a provider, child, supervisor, or alternate loop.
- Why this break is required now: the accepted Slice 6 sequence requires
  durable manual/API wakes before scheduled and webhook ingress. Shipping a
  second direct-execution command would duplicate authority, so manual ingress
  must feed the existing supervisor queue.

## Migration Plan

1. Compatibility window: existing `orket agent submit`, `inspect`, `replay`,
   and `cancel` commands retain their arguments and behavior.
2. Migration steps: point the manual wake command and an explicitly activated
   API supervisor at the same `--db` / `ORKET_GOVERNED_AGENT_DB_PATH`, then
   provide one caller-stable occurrence id and complete dispatch envelope.
3. Validation gates: prove idempotent manual enqueue/list/inspect, source
   provenance, shared validation with API ingress, restart persistence, and
   end-to-end consumption by the API-owned deterministic supervisor.

## Rollback Plan

1. Rollback trigger: manual/API identity collision, bypassed envelope
   validation, direct CLI execution, or a second supervisor owner.
2. Rollback steps: remove the nested wake CLI registration and manual source
   call while retaining the durable queue and API ingress.
3. Data/state recovery notes: already-enqueued manual rows remain valid durable
   work and may still be inspected or consumed through the existing repository
   and supervisor after rollback.

## Versioning Decision

- Version bump type: patch on the next committed core release step.
- Effective version/date: implementation effective 2026-09-07; no versioned
  commit is created unless separately requested.
- Downstream impact: operators gain durable manual enqueue/list/inspect. The
  change does not admit scheduled/webhook ingress, wake recovery mutation,
  generalized wake-driven effects, or new provider behavior.
