# WorkItem Runtime Requirements

Date: 2026-02-24
Status: active

## Objective
Define the CP-4 runtime contract that decouples engine core from fixed card hierarchy semantics while preserving deterministic lifecycle governance.

## Normative Requirements
1. Runtime core entity is `WorkItem`.
2. Required fields:
- `id` (immutable string, workspace-global unique)
- `kind` (profile-defined semantic type)
- `parent_id` (nullable)
- `status` (core state class + profile mapping)
- `depends_on` (optional DAG edges)
- `assignee` (optional)
- `requirements_ref` (optional)
- `verification_ref` (optional)
- `metadata` (optional map)
- `created_at`
- `updated_at`
3. Core state classes:
- `new`
- `ready`
- `in_progress`
- `blocked`
- `done`
- `archived`
4. Lifecycle mutation must use action-based transition API only.
5. Direct state/status writes from executor paths are forbidden.
6. Gate policy checks must execute at transition boundaries:
- pre-transition: auth/dependency/policy
- post-transition: invariant/audit
7. Transition API contract:
- `request_transition(item_id, action, actor, payload)`
- Returns: `result`, `new_state`, optional `gate_request_id`, optional `error_code`
8. Deterministic transition error codes:
- `INVALID_ACTION`
- `DEPENDENCY_UNRESOLVED`
- `APPROVAL_REQUIRED`
- `POLICY_VIOLATION`
- `INVARIANT_FAILED`
9. Existing card behavior must be frozen as profile `legacy_cards_v1`.
10. New default workflow profile must be `project_task_v1`.
11. `project_task_v1` supports 2-level convention with arbitrary depth.
12. Rock/Epic/Issue migration must preserve IDs, status history, and audit traceability.

## Migration Mapping Contract
1. `Rock -> WorkItem(kind=initiative, parent_id=null)`
2. `Epic -> WorkItem(kind=project, parent_id=<rock_id>)`
3. `Issue -> WorkItem(kind=task, parent_id=<epic_id>)`
4. Legacy IDs remain valid aliases only during migration window.
5. Migration must support dry-run artifact output and deterministic rollback path.

## Acceptance Tests
1. `test_workitem_transition_requires_action_api`
2. `test_executor_cannot_set_status_directly`
3. `test_gate_runs_pre_and_post_transition`
4. `test_legacy_cards_profile_parity`
5. `test_project_task_profile_core_flow`
6. `test_migration_rock_epic_issue_mapping_is_lossless`

## Non-Goals
1. Solving all hierarchy presentation preferences in core runtime.
2. Introducing replay as lifecycle policy authority.
3. Deleting legacy profile in CP-4 baseline.
