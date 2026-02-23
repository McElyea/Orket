# Card 003 - LSI Core

## Scope
Define Local Sovereign Index (LSI) behavior and API.

## Deliverables
1. LSI load/validate module.
2. Orphan-check kernel integration.

## Acceptance Criteria
1. Deterministic orphan outcomes.
2. Batch-local exceptions applied correctly.

## Test Gates
1. Orphan violation fixture fails.
2. Valid index fixture passes.

## Dependencies
Cards 001-002.

## Non-Goals
Distributed index federation.
