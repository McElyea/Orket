# Memory Retrieval Trace Schema

## Schema Version
`memory.retrieval_trace.v1`

## Purpose
Define retrieval trace fields required for deterministic replay and equivalence checks.

## Required Retrieval Event Fields
1. `retrieval_event_id`
2. `run_id`
3. `event_id` (linkage to orchestration event)
4. `policy_id`
5. `policy_version`
6. `query_normalization_version`
7. `query_fingerprint`
8. `retrieval_mode` (`text_to_vector` | `vector_direct` | other declared mode)
9. `candidate_count`
10. `selected_records`
11. `applied_filters`
12. `retrieval_trace_schema_version`

## Selected Record Row Fields
1. `record_id`
2. `record_type`
3. `score`
4. `rank`

## Filter Fields
1. `namespace`
2. `tags`
3. `trust`
4. `scope`
5. `ttl`

## Deterministic Ranking Rule
1. Primary ordering: `score` descending.
2. Tie-break ordering: `record_id` ascending.

## Equivalence Enforcement Notes
1. Same retrieval event count.
2. Same `policy_id` and `policy_version`.
3. Same `query_fingerprint`, `query_normalization_version`, and `retrieval_mode`.
4. Same selected record IDs in same rank order.
5. Score value equality is not required for equivalence in `v1` unless later policy overrides it.

## Open Clarifications (Phase 0 Closure Required)
1. Deterministic backend contract (v1):
either backend-native deterministic mode must be enabled,
or retrieval results must pass through deterministic wrapper re-ranking before use.
2. Deterministic wrapper minimum behavior:
stable ranking by score desc + record_id asc tie-break,
and deterministic filter application order.

## Evolution Rules
1. Required field changes require a version increment.
2. Additive optional fields are permitted within `v1`.
