# Memory Determinism Trace Schema

## Schema Version
`memory.determinism_trace.v1`

## Purpose
Define required trace fields for runs that claim deterministic behavior.

## Required Run Envelope Fields
1. `run_id`
2. `workflow_id`
3. `memory_snapshot_id`
4. `visibility_mode`
5. `model_config_id`
6. `policy_set_id`
7. `determinism_trace_schema_version`

## Required Event Fields
1. `event_id` (linkage only; not equivalence-authoritative)
2. `index` (authoritative ordering key)
3. `role`
4. `interceptor`
5. `decision_type`
6. `tool_calls`
7. `guardrails_triggered`
8. `retrieval_event_ids`

## Tool Call Fields
1. `tool_name`
2. `tool_profile_version`
3. `normalized_args`
4. `normalization_version`
5. `tool_result_fingerprint`
6. `side_effect_fingerprint` (when tool profile requires it)

## Required Output Descriptor
1. `output_type`
2. `output_shape_hash`
3. `normalization_version`

## Canonical Output-Shape Examples (Required)
1. Text answer:
`{ "type": "text", "sections": ["intro", "body", "conclusion"] }`
2. Plan or steps:
`{ "type": "plan", "steps": [ { "id": 1, "action": "analyze" }, { "id": 2, "action": "generate" } ] }`
3. Code patch:
`{ "type": "code_patch", "files": [ { "path": "foo.py", "changes": [...] } ] }`

## Equivalence Enforcement Notes
1. Deterministic equivalence is evaluated by event `index` order and required fields.
2. `event_id` is excluded from equivalence matching.
3. Structural/behavioral matching is required; semantic intent matching is out of scope for this schema.

## Retention and Size Baseline (v1)
1. Deterministic run traces must be retained for at least 14 days.
2. Trace artifact size cap is 10 MB per run artifact.
3. If cap is reached, truncation must be explicit and include a truncation marker field in the artifact metadata.

## Evolution Rules
1. Required field changes require a version increment.
2. Additive optional fields are permitted within `v1`.
