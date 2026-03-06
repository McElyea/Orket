# Orket Tool Contract Template

Last updated: 2026-03-06  
Status: Active (governance template)  
Owner: Orket Core

## Purpose

Provide a required contract template for new tools so tool behavior, determinism, schemas, and observability remain governable.

## Template

```yaml
tool_identity:
  tool_name: file.patch
  ring: core # core | compatibility | experimental
  schema_version: 1.0.0
  tool_contract_version: 1.0.0
  tool_registry_version: 1.2.0 # immutable registry snapshot version for run/replay
  mapping_version: null # required when ring == compatibility

capability_profile:
  value: workspace # safe | workspace | system | external

determinism_contract:
  determinism_class: workspace # pure | workspace | external
  side_effect_class: workspace_mutation # none | workspace_mutation | external_mutation

input_schema:
  type: object
  required: [file_path, patch]
  properties:
    file_path:
      type: string
    patch:
      type: string

output_schema:
  type: object
  required: [status]
  properties:
    status:
      type: string
    files_changed:
      type: array
      items:
        type: string

error_schema:
  type: object
  required: [error_code]
  properties:
    error_code:
      type: string
    message:
      type: string

execution_policy:
  timeout_seconds: 30
  retry_policy: none # none | safe_retry
  max_retries: 0

observability:
  required_artifacts:
    - tool_call.json
    - tool_result.json
    - tool_metrics.json
    - tool_invocation_manifest.json
  optional_artifacts:
    - compat_translation.json
    - tool_debug_trace.json
  required_metrics:
    - latency_ms
    - retry_count
    - failure_class
    - determinism_class

compatibility_mapping:
  compatibility_surface_map_path: core/tools/compatibility_map.yaml
  compat_tool_name: openclaw.file_edit
  mapping_version: 1
  schema_compatibility_range: ">=1.0.0 <2.0.0"
  determinism_class: workspace
  mapped_core_tools:
    - workspace.search
    - file.patch
  parity_constraints:
    - functional_output
    - side_effect_surface
    - error_behavior
    - artifact_structure
  semantic_notes: >
    Mimics OpenClaw file edit semantics through Orket core tools.

conformance_tests:
  required:
    - schema_validation_tests
    - determinism_tests
    - error_contract_tests
    - golden_run_tests
```

## Required Rules

1. `tool_name` must be globally unique.
2. `schema_version` follows semantic versioning.
3. `tool_contract_version` must be recorded in `tool_invocation_manifest.json` for every invocation.
4. `tool_registry_version` must match the runtime registry snapshot used for dispatch.
5. `tool_registry_version` must resolve to an immutable snapshot for the full run duration.
6. All tool arguments must be explicit in `input_schema`; no implicit runtime-only parameters.
7. Optional input fields must have deterministic defaults.
8. Error codes must remain stable across minor schema versions.
9. Error codes must use `snake_case`.
10. Only deterministic tools may use retries.
11. Retry policies must avoid repeated side effects.
12. Compatibility mappings cannot elevate determinism class relative to mapped core tools.
13. Compatibility mappings may expand only to core tools and must not chain to compatibility mappings.
14. Compatibility mappings must produce `compat_translation.json`.
15. Tool PRs must include contract, schemas, and conformance tests.

## Suggested Stable Error Codes

1. `file_not_found`
2. `schema_violation`
3. `tool_timeout`
4. `runtime_error`
5. `invalid_args`
6. `determinism_violation`

## Canonical Determinism Ordering

1. `pure > workspace > external`
2. Mapping or run determinism resolves to the least-deterministic class in the composed set.

## Practical Maintenance Tips

1. Run a shared conformance harness per tool (`orket tool-test <tool_name>`).
2. Lint tool registry entries before merge (`orket lint tools`).
3. Maintain a model-to-tool compatibility matrix to separate model faults from tool faults.
4. Keep execution flow staged as `validate -> normalize -> execute -> post-process`.
5. Emit `determinism_violation` artifacts when observed side effects violate declared class.
6. Promote compatibility tools to core only during release windows with replay and parity gates satisfied.
