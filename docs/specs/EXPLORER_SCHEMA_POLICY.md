# Explorer Schema Policy

## Scope
This policy governs explorer artifacts:
1. Frontier explorer (`explorer.frontier.v1`)
2. Context ceiling explorer (`explorer.context_ceiling.v1`)
3. Thermal stability explorer (`explorer.thermal_stability.v1`)

## Required Common Fields
Every explorer artifact must include:
1. `schema_version`
2. `generated_at`
3. `execution_lane`
4. `vram_profile`
5. `provenance`

## Current Schema Versions
1. Frontier: `explorer.frontier.v1`
2. Context ceiling: `explorer.context_ceiling.v1`
3. Thermal stability: `explorer.thermal_stability.v1`

## Evolution Rules
1. Additive-only changes within a major version.
2. No renames or removals of required fields in the same major version.
3. New required fields require a major version increment.
4. Deprecated fields must remain readable for at least one major version after deprecation notice.

## Deprecation Process
1. Add deprecation note in this file and runbook.
2. Add compatibility handling in readers and validators.
3. Add tests that cover old and new versions during transition.
4. Remove deprecated fields only in the next major schema version.

## Contract Enforcement
1. `scripts/check_explorer_schema_contracts.py` is the CI contract gate.
2. Smoke workflow must execute contract tests for all explorer artifacts.
