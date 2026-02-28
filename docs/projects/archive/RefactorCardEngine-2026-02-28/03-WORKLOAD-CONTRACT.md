# RefactorCardEngine Shared Workload Contract v1

Last updated: 2026-02-27

## Contract ID
- `workload.contract.v1`

## Purpose
Define one shared plan shape that both ODR and Cards emit before execution. This is the unification seam for MR-1.

## Required Top-Level Keys
1. `workload_contract_version`
2. `workload_type`
3. `units`
4. `required_materials`
5. `expected_artifacts`
6. `validators`
7. `summary_targets`
8. `provenance_targets`

## Field Notes
1. `workload_contract_version`: exact value `workload.contract.v1`.
2. `workload_type`: `odr` or `cards`.
3. `units`: deterministic execution units.
   - ODR: run pairs (`architect_model`, `auditor_model`, output artifact path).
   - Cards: work items (`card_id`, seat/model assignment, execution params).
4. `required_materials`: files/tools/models required before execution.
5. `expected_artifacts`: artifacts that must exist at postflight.
6. `validators`: deterministic validator keys run after execution.
7. `summary_targets`: paths/files used for operator summary outputs.
8. `provenance_targets`: provenance outputs consumed by index/replay tooling.

## Mapping Guidance
1. Existing ODR arbiter plan fields map directly:
   - `run_pairs` -> `units`
   - `required_materials` -> `required_materials`
   - `expected_artifacts` -> `expected_artifacts`
2. Existing card scheduling/execution map into same shape:
   - selected ready cards -> `units`
   - runtime inputs/dependencies/models -> `required_materials`
   - card logs/results/state snapshots -> `expected_artifacts`
3. No implicit contract fallback. Unknown contract versions must fail closed.

## Schema
- JSON Schema: `docs/projects/RefactorCardEngine/workload-contract-v1.schema.json`
