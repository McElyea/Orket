# Companion Avatar Phase C Implementation Plan (Control-Plane Events)

Last updated: 2026-03-10
Status: In Progress (implementation complete; final phase gate verification pending)
Owner: Orket Core
Canonical lane plan: `docs/projects/Companion/01-AVATAR-POST-MVP-CANONICAL-IMPLEMENTATION-PLAN.md`
Contract authority: `docs/specs/COMPANION_AVATAR_POST_MVP_CONTRACT.md`
Depends on: Phase B speaking-presence baseline completion

## 1. Objective

Add optional expression/gesture control-plane event ingestion without regressing baseline lifecycle truth.

## 2. Scope Deliverables

1. Versioned event envelope ingestion (`avatar_event_v1`).
2. Idempotency-safe event handling.
3. Safe unknown-type and unknown-version handling.
4. Non-blocking expression/gesture mapping to renderer layer.
5. Observability routing, sampling, retention, and redaction defaults.

## 3. Detailed Tasks

### Workstream C1 - Event Envelope Ingestion
Tasks:
1. Implement envelope parser/validator (`type`, `version`, `session_id`, `ts`, `idempotency_key`, `payload`).
2. Add idempotency key dedupe behavior for retried deliveries.
3. Fail closed for unknown versions and ignore unknown event types safely.

Acceptance:
1. malformed events do not crash renderer/state coordinator.
2. duplicate event delivery does not apply side effects more than once.

### Workstream C2 - Expression/Gesture Application
Tasks:
1. Map supported event payloads into renderer-level expression/gesture inputs.
2. Prevent expression events from violating core lifecycle state precedence.
3. Keep baseline behavior unchanged when events are absent.

Acceptance:
1. expression controls are additive.
2. lifecycle truth remains deterministic under competing signals.

### Workstream C3 - Observability Defaults
Tasks:
1. Emit required baseline avatar event vocabulary.
2. Apply sampling and rate-limiting defaults.
3. Apply redaction policy (no content, no secrets, no credential-bearing IDs).
4. Keep high-frequency animation/amplitude data out of normal logs.

Acceptance:
1. required lifecycle and error events are emitted.
2. redaction constraints hold under error and degraded paths.

## 4. Verification Plan

Contract:
1. envelope validation and version handling tests.
2. idempotency dedupe tests.

Integration:
1. expression event path with baseline speaking/lifecycle coexistence.
2. unknown event type/version behavior under real renderer/state flow.

UI behavior:
1. fallback renderer still receives normalized state and remains functional.
2. control events do not break settings/chat/voice controls.

Live:
1. optional event stream connected path.
2. no-event baseline path.
3. malformed/unknown event injection path.

## 5. Completion Gate

Phase C is complete when:
1. versioned envelope ingestion is operational and tested,
2. additive expression behavior is demonstrated without lifecycle regression,
3. observability defaults are implemented and verified,
4. malformed/unknown event handling is safe and non-fatal.

## 6. Execution Checklist Snapshot

1. [x] Workstream C1 event envelope ingestion, fail-closed version handling, and idempotency dedupe.
2. [x] Workstream C2 additive expression/gesture application path with lifecycle precedence preserved.
3. [x] Workstream C3 observability vocabulary, rate-limiting, and payload redaction defaults.
4. [ ] Formal phase closeout/archive handshake in roadmap/docs set (pending while the lane is still executing Phase B and Phase D work).
