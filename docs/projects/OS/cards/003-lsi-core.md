# Card 003 - LSI Core

## Scope
Define Local Sovereign Index (LSI) behavior and API.

## Deliverables
1. LSI load/validate module.
2. Orphan-check kernel integration.
3. Visibility context implementation:
`visible = sovereign_index OR staged_created_set` (links do not create visibility).
4. Identity keys standardized as `{dto_type}:{id}` derived from staged body payloads.

## Acceptance Criteria
1. Deterministic orphan outcomes.
2. Batch-local exceptions applied correctly.
3. Validation path is read-only (no refs/index writes in validate).
4. Tombstone subtraction is identity-based (not stem-only).

## Test Gates
1. Orphan violation fixture fails.
2. Valid index fixture passes.
3. Created-in-same-turn visibility fixture passes.

## Dependencies
Cards 001-002.

## Non-Goals
Distributed index federation.
