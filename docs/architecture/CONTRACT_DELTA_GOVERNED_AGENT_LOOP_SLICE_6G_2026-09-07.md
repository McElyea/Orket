# Contract Delta: Governed Agent Loop Slice 6G

## Summary

- Change title: Authenticated durable webhook wake ingress
- Owner: Orket Core
- Date: 2026-09-07
- Affected contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`

## Delta

- Current behavior: Slice 6A-6F admits manual, API, recovery, and fully
  materialized scheduled wakes, but no supported path authenticates an
  external webhook delivery or retains its delivery identity and replay
  disposition.
- Proposed behavior: add a webhook delivery endpoint beneath the existing
  authenticated `/v1` boundary. Admission additionally requires a configured
  issuer, key id, shared HMAC-SHA256 secret, canonical UTC delivery timestamp,
  a bounded replay window, and a 1 MiB request-body ceiling. The signature covers the contract version,
  issuer, delivery id, timestamp, and raw-body SHA-256 digest. The durable
  delivery receipt and selected `source=webhook` wake publish atomically. Exact
  delivery replay is idempotent; changed content or metadata under a retained
  delivery identity conflicts without changing prior truth. Secrets and raw
  signatures are neither persisted nor projected.
- Why this break is required now: treating webhook bodies as ordinary API
  wakes would omit external identity, freshness, and replay evidence. Webhook
  authentication and durable delivery admission must precede supervisor
  dispatch.

## Migration Plan

1. Compatibility window: existing manual, API, recovery, schedule, queue,
   control, inspection, and supervisor contracts remain unchanged.
2. Migration steps: configure one issuer, key id, and HMAC secret; send a
   canonical UTC timestamp and `sha256=<lowercase hex>` signature; reuse a
   stable delivery id for retries of identical raw content only.
3. Validation gates: prove API-key and HMAC enforcement, issuer/key binding,
   timestamp freshness and future-skew rejection, invalid JSON rejection after
   authentication, atomic delivery/wake publication, exact replay,
   contradictory replay, restart persistence, source-path confinement,
   inspection projection, and supervisor consumption through a real external
   child process.

## Rollback Plan

1. Rollback trigger: webhook admission accepts an unauthenticated, stale,
   contradictory, or route-rebound delivery; loses a receipt; leaks signing
   material; or produces duplicate wakes.
2. Rollback steps: disable or remove webhook route composition while retaining
   delivery receipts and already admitted wakes for inspection.
3. Data/state recovery notes: do not delete admitted webhook wakes. Cancel or
   reconcile them through the existing wake-control contract.

## Versioning Decision

- Version bump type: patch on the next committed core release step.
- Effective version/date: implementation effective 2026-09-07; no versioned
  commit is created unless separately requested.
- Downstream impact: webhook callers gain one authenticated durable ingress
  contract. Generalized wake-driven effects remain outside this delta.
