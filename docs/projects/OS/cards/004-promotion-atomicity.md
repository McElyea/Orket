# Card 004 - Promotion Atomicity

## Scope
Codify promotion rules and atomic commit/reject behavior.

## Deliverables
1. Promotion state contract.
2. Atomic transition implementation notes.

## Acceptance Criteria
1. No partial promotion states.
2. Recovery path is deterministic.

## Test Gates
1. Promotion crash recovery test.
2. No-partial-commit test.

## Dependencies
Card 003.

## Non-Goals
Cross-cluster consensus.
