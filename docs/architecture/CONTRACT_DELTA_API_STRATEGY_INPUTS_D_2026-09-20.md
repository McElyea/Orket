# Captured API strategy inputs and truthful archive projection

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version: 0.6.50 candidate, 2026-09-20.
- Durable contract: `docs/specs/API_STRATEGY_INPUTS.md`.

## Delta and migration
Archive selectors previously borrowed request lists, and later effects reread
mutable request fields across awaits. Response normalization could report a count
unrelated to completed operations. Application now retains selectors/actor/reason
at entry, passes optional tuples to selector strategies, and validates archive
response claims against the actual accumulated results. Extra JSON presentation
fields and ordering remain supported; contradictory reserved fields are refused.
Earlier archive commits survive a later recommendation refusal.

Custom metrics strategies accept SDK FrozenJson. Explorer sorters and chained
preview strategies accept immutable sequences/read-only mappings. Invocation
recommendations use JSON arguments and are copied before intervening awaits.
Websocket policy implementations accept an error-category string, not an exception.
Boolean decisions require booleans. No old-signature retry is introduced.

## Verification and rollback
Retain real SQLite/ASGI pre-change selector-expansion, held-request mutation and
false-count counterexamples. Cover nested mutation, held preview/event publication,
strict recommendation refusal and prior-version supported defaults. Run affected
source/installed API flows with exact package origins and owned cleanup.
The canonical plan records observed proof and limits; no broad API acceptance or
hostile-code containment is implied.

Rollback inputs, callers, custom policies and their tests together. Preserve
completed archive transactions and historical evidence. A rollback must not
reclassify a contradictory count as verified archive success.

## Versioning decision
- Patch remediation checkpoint with an explicit breaking API-strategy contract.
- Remaining D boundaries, E/CAP and whole-lane acceptance remain open.
