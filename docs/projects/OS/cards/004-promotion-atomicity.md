# Card 004 - Promotion Atomicity

## Scope
Codify promotion rules and atomic commit/reject behavior.

## Deliverables
1. Promotion state contract.
2. Atomic transition implementation notes.
3. Tombstone parser + strict payload validation.
4. Run ledger integration (`committed/index/run_ledger.json`).

## Acceptance Criteria
1. No partial promotion states.
2. Recovery path is deterministic.
3. Missing/empty staging root resolves as deterministic no-op or deletion-only promotion.
4. Promotion emits canonical ordering/deletion error and info codes.

## Test Gates
1. Promotion crash recovery test.
2. No-partial-commit test.
3. Tombstone wire-format vectors pass.
4. No-op promotion fixture emits `I_NOOP_PROMOTION`.

## Dependencies
Card 003.

## Non-Goals
Cross-cluster consensus.
