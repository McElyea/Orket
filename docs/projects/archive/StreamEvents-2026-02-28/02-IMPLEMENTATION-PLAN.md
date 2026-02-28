# Stream Events Implementation Plan

## Objective
Deliver low-latency streamed NPC interaction while preserving deterministic boundary commits for authoritative state changes.

## Phase 1: Contracts and Event Taxonomy
1. Define stream event schema and versioning:
- event envelope (`event_id`, `session_id`, `turn_id`, `timestamp`, `type`, `payload`)
- initial event types from requirements (`turn_accepted`, `model_loading`, `token_delta`, `turn_final`, etc.)
2. Define `InteractionSession` contract:
- `start_turn()`
- `publish_event()`
- `cancel_turn()`
- `finalize_turn()`
3. Document authoritative vs non-authoritative event classes.

## Phase 2: Interaction Manager Runtime
1. Add `InteractionManager` runtime component:
- own active interaction sessions
- manage stream subscriptions
- route cancellation/interrupt signals
2. Add transport adapter (initial):
- WebSocket endpoint for local client streaming
3. Add backpressure policy:
- bounded per-session event queue
- deterministic overflow behavior (drop-policy or fail-policy)

## Phase 3: Authority Plane Integration
1. Bridge turn finalization to authoritative execution/commit path:
- ExtensionManager workload execution finalization
- governance checks
- provenance generation
2. Ensure streamed `turn_final` remains preview/non-authoritative until boundary commit succeeds.
3. Emit explicit authority commit outcomes:
- `commit_succeeded`
- `commit_failed`

## Phase 4: Model Lifecycle and Latency Handling
1. Add model lifecycle stream hooks:
- selected/loading/ready/switching
2. Add warm-pool interface seam for local model processes:
- initial no-op/default implementation allowed
3. Add predictive prewarm trigger seam (optional feature flag in v1).

## Phase 5: Tests and Replay Semantics
1. Add tests for:
- immediate ACK timing path
- cancel/interrupt correctness
- no partial-output mutation
- finalization boundary commit behavior
2. Add replay semantics:
- stream deltas marked telemetry
- authoritative artifacts remain canonical for audits/replay

## Deliverables
1. New stream project docs and schema definitions.
2. `InteractionManager` + `InteractionSession` runtime components.
3. WebSocket streaming interface for interaction events.
4. Integration with ExtensionManager/authority commit path.
5. Test suite covering interaction and authority boundary invariants.

## Risks and Mitigations
1. Risk: Streaming complexity leaks into authority logic.
- Mitigation: hard separation of planes with explicit boundary API.
2. Risk: Model switching causes perceived stalls.
- Mitigation: immediate lifecycle events + warm-pool seam.
3. Risk: Event flood/backpressure instability.
- Mitigation: bounded queues + deterministic overflow policy.

## Exit Criteria
1. End-to-end interactive NPC turn streams instantly and cancels cleanly.
2. World-state mutation only occurs at authority boundaries.
3. Reliable Mode guarantees remain intact for committed outcomes.
4. Stream telemetry and authoritative artifacts are clearly separated in runtime and docs.
