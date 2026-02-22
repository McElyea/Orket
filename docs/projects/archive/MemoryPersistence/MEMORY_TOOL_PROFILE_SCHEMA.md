# Memory Tool Profile Schema

## Schema Version
`memory.tool_profile.v1`

## Purpose
Define per-tool fingerprint ownership so field selection is explicit and versioned.

## Required Tool Profile Fields
1. `tool_name`
2. `tool_profile_version`
3. `normalized_args_fields`
4. `tool_result_fingerprint_fields`
5. `side_effect_fingerprint_fields`
6. `hash_algorithm` (default `sha256` for v1)
7. `normalization_version` (must reference `json-v1` for v1 contracts)

## Semantics
1. `normalized_args_fields` defines exact argument fields included in deterministic matching.
2. `tool_result_fingerprint_fields` defines exact result fields included in `tool_result_fingerprint`.
3. `side_effect_fingerprint_fields` defines exact side-effect fields included when side effects are in scope.
4. Ad hoc field selection is prohibited; tool profile governs all fingerprint input selection.

## Runtime Requirements
1. `tool_profile_version` must be logged for each tool call.
2. Tool runtime profile hash must include tool profile versions for all enabled tools.
3. Deterministic equivalence assumes matching tool profile versions.

## Evolution Rules
1. Any change to included field sets requires a tool profile version bump.
2. Deprecated fields may remain readable but must not silently alter fingerprint semantics in the same version.
