# Contract Delta: Governed Agent Loop Slice 6B

## Summary

- Change title: API-owned continuous-agent production composition
- Owner: Orket Core
- Date: 2026-09-07
- Affected contracts: `docs/specs/GOVERNED_AGENT_LOOP_V1.md` and
  `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`

## Delta

- Current behavior: Slice 6A provides a durable manual/API/recovery wake table,
  fenced claims, recovery rules, a bounded supervisor, and a container teardown
  seam, but no public wake transport or production loop composition.
- Proposed behavior: admit authenticated API wake persistence and explicit
  opt-in API lifespan processing. Each app owns its governed-agent repositories,
  inspector, dispatcher, supervisor, renewal task, and teardown. A claimed wake
  resolves the canonical extension workload and invokes the same bounded loop,
  child adapter, broker, provider selection, verifier, and final-truth path as
  the CLI. Durable claim count enforces the configured provider/local capacity,
  and the claim guard is rechecked before broker and result publications.
  Uncertain claimed or cancelled work retains its capacity reservation until
  explicit reconciliation rather than admitting an unsafe replacement.
- Why this break is required now: continuous operation needs a real composition
  root and transport only after architectural-truth B2 removed module-default
  API ownership. Leaving the queue detached would preserve durable work without
  an admitted production consumer.

## Migration Plan

1. Compatibility window: bounded CLI commands remain unchanged. API supervisor
   processing is disabled by default, so existing API deployments do not begin
   provider or child work after upgrade.
2. Migration steps: configure the shared governed-agent SQLite path, exact
   provider/model posture, one consistent capacity across all processes sharing
   that database, claim lease and renewal bounds, then set
   `ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED=1`. Submit only complete
   `governed_agent_wake_dispatch.v1` payloads through authenticated `/v1`.
3. Validation gates: prove idempotent API persistence across app reconstruction,
   real child/broker/final-truth dispatch, existing terminal-run non-reopening,
   capacity refusal, lease renewal, stale provider-result fencing, composed
   inspection/replay, dependency direction, async safety, and clean teardown.

## Rollback Plan

1. Rollback trigger: lifecycle task leakage, duplicated dispatch, stale result
   publication, capacity oversubscription, or API authority drift.
2. Rollback steps: disable `ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED` first, then
   revert the API router and per-app runtime registration while retaining the
   Slice 6A repository.
3. Data/state recovery notes: queued and claimed wake rows remain durable.
   Claimed or uncertain rows must follow the existing explicit stop and effect
   reconciliation gate; rollback must not blindly requeue them.

## Versioning Decision

- Version bump type: patch on the next committed core release step.
- Effective version/date: implementation effective 2026-09-07; no versioned
  commit is created by this slice unless separately requested.
- Downstream impact: API clients gain authenticated wake and read-only inspector
  routes. Scheduled/webhook ingress, public manual-wake transport, generalized
  wake-driven effects, and live Ollama supervisor claims remain unadmitted.
