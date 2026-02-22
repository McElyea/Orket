# Skill Loader Error Schema

Version: `skill.loader_error.v1`  
Last updated: 2026-02-21

## Purpose
Define canonical structured error payloads when Skill loading fails.

## Loader Behavior
If a Skill violates contract requirements, loader MUST:
1. reject the Skill
2. return a structured error payload

## Required Error Fields
A loader rejection payload MUST include:
1. `error_code`
2. `message`
3. `skill_id`
4. `skill_version`
5. `skill_contract_version_seen`
6. `validation_stage`
7. `retryable`

Optional:
1. `entrypoint_id`

## Canonical Error Codes
1. `ERR_CONTRACT_INVALID`
2. `ERR_SCHEMA_INVALID`
3. `ERR_PERMISSION_UNDECLARED`
4. `ERR_FINGERPRINT_INCOMPLETE`
5. `ERR_RUNTIME_UNPINNED`
6. `ERR_SIDE_EFFECT_UNDECLARED`
7. `ERR_CONTRACT_UNSUPPORTED_VERSION`
8. `ERR_VALIDATION_INTERNAL`

## Error Semantics
1. `retryable` MUST indicate whether reattempt may succeed without contract changes.
2. `validation_stage` SHOULD identify where failure occurred (schema, fingerprint, permissions, runtime, loader).
3. Unsupported contract version MUST use `ERR_CONTRACT_UNSUPPORTED_VERSION`.

## Validation Output Compatibility
Loader errors should align with validation outputs from Skill validation metadata:
1. `contract_valid`
2. `determinism_eligible`
3. `fingerprint_completeness`
4. `permission_risk`
5. `side_effect_risk`
6. `validation_policy_version`

