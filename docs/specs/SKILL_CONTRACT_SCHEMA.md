# Skill Contract Schema

Version: `skill.contract.v1`  
Last updated: 2026-02-21

## Purpose
Define the canonical Skill manifest contract for the Orket Local Skill Runtime (LSR).

## Required Top-Level Fields
Every Skill manifest MUST include:
1. `skill_contract_version`
2. `skill_id`
3. `skill_version`
4. `description`
5. `manifest_digest`
6. `entrypoints`

## Identity and Immutability
1. `(skill_id, skill_version)` MUST be immutable for contract + observable behavior.
2. `manifest_digest` MUST include algorithm prefix (example: `sha256:<hex>`).
3. Optional additional identity digests:
   - `content_digest`
   - `source_commit_digest`

## Entrypoint Contract
Each `entrypoints[*]` item MUST include:
1. `entrypoint_id`
2. `runtime` (`python`, `node`, `shell`, `container`)
3. `runtime_version` (required for pinned runtimes in deterministic mode)
4. `command` (or module reference)
5. `working_directory`
6. `runtime_limits` (for example: `max_execution_time`, `max_memory`)
7. `input_schema`
8. `output_schema`
9. `error_schema`
10. `args_fingerprint_fields`
11. `result_fingerprint_fields`
12. `side_effect_fingerprint_fields`
13. `side_effect_categories`
14. `requested_permissions`
15. `required_permissions`
16. `tool_profile_id`
17. `tool_profile_version`

## Execution Context Contract
Entrypoints MUST declare or inherit deterministic execution context assumptions:
1. `required_environment_variables`
2. `value_fingerprints` (optional)
3. locale/timezone/encoding assumptions
4. deterministic working directory

Hidden execution context MUST NOT influence behavior.

## Determinism Eligibility Inputs
Requested determinism is advisory via `requested_determinism_profile`.

Effective `determinism_eligible` is derived by Orket from:
1. schema validity
2. runtime pinning
3. fingerprint completeness
4. side-effect fingerprint coverage
5. permission declarations

## Side-Effect Category Rules
1. Core categories are a closed set versioned with `skill_contract_version`.
2. Namespaced extensions are allowed as `vendor.category_name`.
3. Extensions MUST NOT redefine or alias core categories.

## Loader Compatibility
Invalid contract payloads MUST be rejected by loader policy and surfaced through canonical loader errors.

Companion schema doc:
1. `docs/specs/SKILL_LOADER_ERROR_SCHEMA.md`
