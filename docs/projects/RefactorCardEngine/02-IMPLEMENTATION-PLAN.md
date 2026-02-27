# RefactorCardEngine Implementation Plan

Last updated: 2026-02-27

## Execution Principle
Do not run hierarchy migration and framework unification simultaneously. Land seam first, then move structure.

## Phase 1: Workload Contract Unification (MR-1)
Objective: one shared execution shell for Cards and ODR.

### Slice 1.1 - Shared Contract Spec
1. Add shared workload contract schema/spec doc under `docs/projects/RefactorCardEngine/`.
2. Map current ODR plan fields and card plan fields to this shape.
3. Add explicit version field and required key checks.

### Slice 1.2 - ODR Adapter
1. Implement ODR adapter that emits shared contract without changing ODR round semantics.
2. Keep current ODR tooling outputs stable (`index.json`, `provenance.json`, run JSON).
3. Add tests for contract emission shape.

### Slice 1.3 - Card Adapter
1. Implement card adapter that emits shared contract for existing card workflows.
2. Preserve legacy card behavior while compiling through shared plan shape.
3. Add tests covering material/validator/artifact declarations.

### Slice 1.4 - Shared Arbiter Path
1. Route both adapters through shared preflight/execution/postflight shell.
2. Keep deterministic error artifacts and provenance hooks common.
3. Add integration tests validating both workload types through same shell.

## Phase 2: Card Hierarchy Refactor (MR-2)
Objective: remove hard three-layer structural constraint while preserving familiar views.

### Slice 2.1 - Data Model Extension
1. Introduce/normalize `parent_id`, `kind`, and profile metadata in card records.
2. Keep legacy fields mapped and readable.
3. Add migration dry-run report for legacy Rock/Epic/Issue to parent-tree mapping.

### Slice 2.2 - Profile Views
1. Add `legacy_cards_v1` view/profile mapping (Rock/Epic/Issue).
2. Add `project_task_v1` mapping (2-level default convention, unlimited depth supported).
3. Ensure views are projections over same underlying tree, not separate stores.

### Slice 2.3 - Execution Compatibility
1. Confirm card execution reads from profile projection but writes to canonical parent-tree model.
2. Ensure existing CLI/API surfaces still function with legacy profile default.
3. Add tests for status transitions and dependency behavior under both profiles.

### Slice 2.4 - Cutover Guard
1. Add explicit migration/cutover guard checks (data shape + profile resolution).
2. Define rollback path to legacy profile if required.
3. Document post-cutover operational runbook updates.

## Deliverables
1. Shared workload contract docs and validators.
2. ODR and Cards adapters to shared contract.
3. Parent-tree card model with legacy and new profile projections.
4. Regression and integration test coverage for both phases.

## Risks and Mitigations
1. Risk: semantic drift during dual-path period.
   - Mitigation: contract shape tests and deterministic artifact diff checks.
2. Risk: card migration complexity.
   - Mitigation: dry-run mappings + profile-based rollout.
3. Risk: confusing mode boundaries.
   - Mitigation: ODR explicitly documented as workload mode, not parallel framework.

## Exit Criteria
1. ODR and Cards execute via one shared shell.
2. Card hierarchy no longer structurally limited to three fixed levels.
3. Legacy view remains available and validated during migration window.
4. No regression in deterministic ODR artifact behavior.
