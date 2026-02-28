# Card 003 - LSI Core

## Scope
Define Local Sovereign Index (LSI) behavior and API.

## Deliverables
1. LSI load/validate module.
2. Orphan-check kernel integration.
3. Visibility context implementation:
`visible = sovereign_index OR staged_created_set` (links do not create visibility).
4. Identity keys standardized as `{dto_type}:{id}` derived from staged body payloads.
5. Tombstone subtraction implemented on identity keys (`{dto_type}:{id}`), not stem-only keys.

## Acceptance Criteria
1. Deterministic orphan outcomes.
2. Batch-local exceptions applied correctly.
3. Validation path is read-only (no refs/index writes in validate).
4. Tombstone subtraction is identity-based (not stem-only).
5. Staged envelope metadata does not override identity; identity always comes from staged body payload.
6. Orphan failures emit `E_LSI_ORPHAN_TARGET` with pointer-rooted `/links/...` locations.

## Test Gates
1. Orphan violation fixture fails.
2. Valid index fixture passes.
3. Created-in-same-turn visibility fixture passes.
4. Self-authorization regression fixture fails (links alone cannot create visibility).

## Dependencies
Cards 001-002.

## Non-Goals
Distributed index federation.
