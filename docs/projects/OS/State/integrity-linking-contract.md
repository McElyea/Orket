# Integrity Linking Contract (v1)

Last updated: 2026-02-22
Status: Normative

## Scope
Defines sovereign referential integrity for links emitted by kernel validation.

## Rules
1. Each reference target must exist in sovereign index or local batch IDs.
2. Unknown targets are rejected with deterministic failure code:
`E_ORPHAN_LINK_VIOLATION`.
3. Missing/invalid index source is fail-closed:
`E_ORPHAN_INDEX_UNAVAILABLE`.
4. Relationship checks and orphan checks are both required for promotion.

## Resolution Semantics
1. Local batch IDs are IDs explicitly introduced in the current staged batch, not IDs inferred from link table side effects.
2. Orphan validation MUST NOT treat staged `refs/by_id` entries as proof of existence by themselves.
3. Resolution order is deterministic:
local batch IDs first, then sovereign committed index.
4. If neither source contains target, validation MUST fail with pointer-rooted location under `/links`.

## Visibility Model (Normative)
1. `visible(target) = in_sovereign_index(target) OR in_staged_created_set(target)`.
2. `staged_created_set` MUST be derived from staged body/manifest creation records only.
3. Links MUST NOT create visibility.
4. Validation MUST NOT self-authorize targets by inserting them into ref tables during the same validation.

## Required Orphan Behavior
1. If target is not visible by model above, validation MUST fail `E_LSI_ORPHAN_TARGET`.
2. Created-in-same-turn targets MUST pass if present in `staged_created_set`.
3. Targets deleted in current turn MUST be treated as not visible after promotion.
