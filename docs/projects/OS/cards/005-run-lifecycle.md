# Card 005 - Run Lifecycle

## Scope
Implement run/turn lifecycle state machine as kernel contract.

## Deliverables
1. Run state transitions.
2. Failure persistence semantics.

## Acceptance Criteria
1. Sequential enforcement holds.
2. Invalid transitions rejected with deterministic codes.

## Test Gates
1. Lifecycle transition tests.
2. Crash recovery state tests.

## Dependencies
Cards 001-004.

## Non-Goals
Scheduler redesign.
