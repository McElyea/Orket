# Run Lifecycle Contract (v1)

Last updated: 2026-02-22
Status: Normative

## IDs
1. `run_id`: string, unique per run.
2. `turn_id`: string, unique within `run_id`.
3. `workflow_id`: string, stable for replay scope.

## State Machine
`RUN_CREATED -> TURN_STAGED -> TURN_VALIDATED -> TURN_PROMOTED -> RUN_COMPLETED`

Failure states:
1. `RUN_FAILED`
2. `TURN_REJECTED`
3. `PROMOTION_REJECTED`

## Rules
1. Turn progression is sequential per run.
2. Promotion occurs only after validation success.
3. Invalid promotion attempts are rejected and logged.
4. Crash recovery must persist last durable state.
5. Cleanup of staging artifacts is policy-controlled and auditable.

## Run Lifecycle + Promotion Semantics (Closure)

### Definitions
1. Run workspace: canonical workspace containing committed state for a run.
2. Staging area: per-turn shadow workspace where mutations are prepared.
3. Promotion: atomic operation that applies one turn's staged delta to sovereign state.
4. Turn ordering: strict sequence with no gaps.
5. Stem: logical triplet root (unit of state).
6. Tombstone: explicit record that a stem is deleted at a specific turn.
7. Delete-stem: explicit removal action represented by a tombstone.

### Law 2: Sequential Promotion Enforcement
1. `turn-N` MUST NOT be promoted unless `turn-(N-1)` is already promoted.
2. Runtime MUST persist `last_promoted_turn_id` in sovereign run metadata.
3. Promotion MUST compute `next_expected_turn_id(last_promoted_turn_id)` and compare to requested turn.
4. On mismatch, runtime MUST fail with `E_PROMOTION_OUT_OF_ORDER`.
5. Re-promoting an already promoted turn SHOULD fail with `E_PROMOTION_ALREADY_APPLIED`.

Test requirements:
1. Promote `turn-0002` with last promoted `turn-0000` -> `FAIL E_PROMOTION_OUT_OF_ORDER`.
2. Promote `turn-0001`, then `turn-0002` -> PASS.
3. Promote same turn twice -> `FAIL E_PROMOTION_ALREADY_APPLIED`.

### Law 6: Deletion Semantics (Explicit, Not Silent Absence)
1. Deletion MUST be represented by explicit deterministic transition data in staging.
2. Silent absence is not a valid deletion signal.
3. v1 canonical delete signal is tombstones. `delete_stem[]` directives are deprecated as a primary signal.
4. Tombstone wire format is normative in `Execution/tombstone-wire-format-v1.md`.

### Promotion Behavior for Missing/Empty Staging Root
1. If staging root is missing or empty AND no explicit delete directives/tombstones exist:
treat as no-op promotion and PASS, while still advancing turn chain.
2. If staging root is missing or empty AND explicit delete directives/tombstones exist elsewhere:
perform deletion-only promotion and PASS.
3. If staging state is malformed:
FAIL with deterministic promotion failure code.

### Pruning Rule for Delete-Stem
1. Promotion MUST remove sources for deleted stem from `refs/by_id`.
2. Pruning MUST be stem-scoped and deterministic.
3. Resulting ref records MUST remain canonicalized and sorted.
4. On delete promotion, implementation MUST either:
remove the stem index record, OR mark it tombstoned (single implementation path required).
5. Tombstoned targets MUST be treated as not visible by link integrity unless explicitly permitted by policy.

## Required Error Codes
1. `E_PROMOTION_OUT_OF_ORDER`
2. `E_PROMOTION_ALREADY_APPLIED`
3. `E_LSI_ORPHAN_TARGET`
4. `E_PROMOTION_STAGE_MISSING` (only if implementation chooses fail instead of no-op)
5. `E_DELETE_MISSING_TOMBSTONE` (only if implementation requires explicit tombstone evidence)
