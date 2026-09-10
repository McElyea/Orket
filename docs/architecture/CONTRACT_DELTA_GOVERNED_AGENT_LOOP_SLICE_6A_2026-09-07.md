# Contract Delta: Governed Agent Loop Slice 6A

Date: 2026-09-07
Status: Implemented bounded substrate; production activation not admitted
Owner: Orket Core

## Trigger

The accepted Slice 6 sequence requires durable manual/API wakes and recovery
before scheduled or webhook ingress. Architectural-truth B2 still prevents
truthful production ownership of a continuous API supervisor, but it does not
prevent implementing and proving the durable queue, claim, fencing, recovery,
inspection, and application-container teardown primitives independently.

## Previous Behavior

1. Agent work could begin only through synchronous bounded CLI submission.
2. No durable wake or claim record existed.
3. There was no atomic capacity-aware claim boundary or wake fencing generation.
4. Agent inspection could not explain wake or dispatch-claim state.
5. The API runtime container owned tasks and its engine but had no general
   registered-resource teardown seam.

## Accepted Slice 6A Behavior

1. One SQLite `governed_agent_wakes` queue accepts only `manual`, `api`, and
   `recovery` source tokens in this increment.
2. Stable wake identity plus `(source, deduplication_key)` make equivalent
   enqueue idempotent and contradictory reuse a conflict.
3. `BEGIN IMMEDIATE` transactions serialize capacity checks and queued-to-claim
   compare-and-set transitions across repository instances.
4. Claims contain owner identity, an expiry, cancellation epoch, and a
   monotonically increasing fencing generation.
5. Claim validation gates dispatch and publication. Release followed by reclaim
   invalidates the earlier owner even when stale computation continues.
6. Expiry moves a claim to `recovery_required`; expiry alone never redispatches.
   Requeue requires both confirmed child stop and cleared effect uncertainty.
7. Cancellation invalidates an active claim and retains uncertainty when the
   claimed worker has not been proven stopped.
8. One event-driven application supervisor dispatches at most one bounded queue
   action per cycle and turns cancellation or bounded failures into durable
   recovery truth.
9. `ApiRuntimeContainer` can own registered resources and closes tasks,
   resources, and engine without abandoning later teardown after one failure.
10. Existing-run inspection includes wake source, occurrence, state, owner,
    lease, generation, cancellation epoch, uncertainty, result, and reason.

## Explicit Non-Admission

This delta does not admit:

1. a public manual or HTTP API wake endpoint;
2. production supervisor startup from API lifespan;
3. wake-driven invocation of the existing agent loop, broker, provider, or
   effect service;
4. a claim that the current broker/effect fence is already bound to wake
   generation;
5. scheduled ingress, timezone/missed-trigger policy, webhook authentication,
   or webhook replay protection;
6. full Slice 6 completion or continuous-operation proof.

## Migration and Rollback

The queue table is additive and created lazily in the selected governed-agent
SQLite database. Existing agent runs and tables are unchanged. Rollback removes
the unused Slice 6A code and projection; no public ingress currently creates
production wake records. Retaining the table is harmless additive state.

## Verification Boundary

Integration proof uses two independent repositories over a real SQLite file,
concurrent claims, process-lifetime repository reconstruction, cancellation,
expiry, explicit recovery, inspector reconstruction, event-driven supervisor
dispatch, and application-container shutdown. It is not live provider or public
API proof.
