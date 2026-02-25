# WorkItem Runtime Implementation Slices

Date: 2026-02-24
Status: active
Execution mode: deterministic vertical slices

## Canonical Sequence
1. CP-4.1 WorkItem core contract and transition API
2. CP-4.2 Profile system and legacy freeze
3. CP-4.3 `project_task_v1` default profile
4. CP-4.4 Gate boundary consolidation
5. CP-4.5 Migration and cutover safety

## CP-4.1 WorkItem Core Contract and Transition API
Objective:
Introduce profile-agnostic lifecycle contract and deterministic transition interface.

Definition of Ready:
1. Core schema fields and invariants agreed.
2. Error code list fixed.
3. Existing direct status mutation paths inventoried.

Implementation:
1. Add core `WorkItem` schema and invariants.
2. Add transition service contract and result envelope.
3. Route runtime lifecycle writes through transition contract.
4. Fail closed for direct status writes.

Acceptance:
1. `test_workitem_transition_requires_action_api`
2. `test_executor_cannot_set_status_directly`

## CP-4.2 Profile System and Legacy Freeze
Objective:
Extract existing hierarchy and transition behavior into `legacy_cards_v1`.

Definition of Ready:
1. Legacy lifecycle behavior baseline captured in regression fixtures.

Implementation:
1. Add workflow profile interface.
2. Implement `legacy_cards_v1` adapter from existing behavior.
3. Bind runtime to resolved profile instead of hardcoded hierarchy logic.

Acceptance:
1. `test_legacy_cards_profile_parity`

## CP-4.3 New Default Profile (`project_task_v1`)
Objective:
Provide a simple default profile with arbitrary depth support.

Definition of Ready:
1. Core state classes and blocked-reason rule agreed.

Implementation:
1. Add `project_task_v1` transitions and mapping.
2. Require reason payload for blocked action.
3. Set profile default to `project_task_v1` behind switch flag.

Acceptance:
1. `test_project_task_profile_core_flow`

## CP-4.4 Gate Boundary Consolidation
Objective:
Make transition boundaries the authoritative lifecycle policy layer.

Definition of Ready:
1. Pre/post boundary checks mapped from existing gate logic.

Implementation:
1. Move auth/dependency/policy checks to pre-transition.
2. Move invariant/audit checks to post-transition.
3. Keep executor outcome-only and remove lifecycle policy branching.

Acceptance:
1. `test_gate_runs_pre_and_post_transition`

## CP-4.5 Migration and Cutover Safety
Objective:
Migrate Rock/Epic/Issue artifacts to WorkItem model without losing traceability.

Definition of Ready:
1. Migration mapping approved.
2. Dry-run artifact schema approved.

Implementation:
1. Implement mapper and dry-run report.
2. Preserve identity and lifecycle history in migration output.
3. Add deterministic rollback plan.
4. Promote default profile only after parity + migration suite is green.

Acceptance:
1. `test_migration_rock_epic_issue_mapping_is_lossless`

## Required Validation Commands (Each Slice Exit)
1. `python scripts/check_dependency_direction.py --legacy-edge-enforcement fail`
2. `python scripts/check_volatility_boundaries.py`
3. `python -m pytest -q`
