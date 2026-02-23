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
