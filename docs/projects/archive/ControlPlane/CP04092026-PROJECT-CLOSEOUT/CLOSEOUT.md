# ControlPlane Project Closeout

Last updated: 2026-04-09
Status: Completed
Owner: Orket Core

Archived lane authority:
1. `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CONTROL_PLANE_PROJECT_CLOSEOUT_READINESS_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/README.md`

Active durable authorities:
1. `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`
2. `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`

Historical context:
1. `docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/CLOSEOUT.md`
2. `docs/projects/archive/ControlPlane/CP04092026-CONVERGENCE-REOPEN-CLOSEOUT/CLOSEOUT.md`
3. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CLOSEOUT.md`
4. `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/CLOSEOUT.md`

## Outcome

The active ControlPlane queue formerly tracked in `Priority Now` is closed.

Closeout facts:
1. `CP0` extracted the durable glossary and requirement authority into `docs/specs/`.
2. The required `CP1` through `CP6` proof sets remained green on `2026-04-09` without additional runtime code changes, so those slices closed as already satisfied by the current codebase.
3. `CP7` archived the closeout-readiness record, promoted the governed start-path matrix into `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`, and removed the non-archive `docs/projects/ControlPlane/` shell.
4. Future ControlPlane implementation work must reopen explicitly through `docs/ROADMAP.md` instead of continuing from stale project-local queue state.

## Verification

Proof type: `structural`
Observed path: `primary`
Observed result: `success`

Executed proof:
1. `python scripts/governance/check_docs_project_hygiene.py` (pass)
2. `python -m pytest -q tests/platform/test_current_authority_map.py` (`7 passed`)
3. `python -m pytest -q tests/contracts/test_control_plane_reservation_contract.py tests/contracts/test_control_plane_lease_contract.py` (`20 passed`)
4. `python -m pytest -q tests/interfaces/test_coordinator_api_control_plane.py tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py tests/interfaces/test_api_approvals.py` (`21 passed`)
5. `python -m pytest -q tests/integration/test_orchestrator_scheduler_control_plane.py tests/integration/test_gitea_state_worker_control_plane.py tests/application/test_control_plane_target_resource_refs.py` (`15 passed`)
6. `python -m pytest -q tests/contracts/test_control_plane_effect_journal_contract.py tests/application/test_control_plane_publication_service.py` (`20 passed`)
7. `python -m pytest -q tests/runtime/test_protocol_receipt_materializer.py tests/runtime/test_run_summary_packet1.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_artifact_provenance.py tests/scripts/test_common_run_summary_support.py` (`32 passed`)
8. `python -m pytest -q tests/integration/test_turn_executor_control_plane_evidence.py tests/integration/test_turn_tool_control_plane_closeout.py tests/integration/test_orchestrator_issue_control_plane.py` (`14 passed`)
9. `python -m pytest -q tests/contracts/test_control_plane_recovery_contract.py tests/application/test_sandbox_control_plane_checkpoint_service.py` (`13 passed`)
10. `python -m pytest -q tests/application/test_kernel_action_control_plane_pre_effect_recovery.py tests/integration/test_sandbox_runtime_recovery_service.py` (`13 passed`)
11. `python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py` (`16 passed`)
12. `python -m pytest -q tests/interfaces/test_api_nervous_system_operator_surfaces.py tests/application/test_tool_approval_control_plane_operator_service.py` (`8 passed`)
13. `python -m pytest -q tests/application/test_pending_gate_control_plane_operator_service.py tests/application/test_kernel_action_control_plane_operator_service.py` (`4 passed`)
14. `python -m pytest -q tests/integration/test_sandbox_lifecycle_reconciliation_service.py tests/integration/test_gitea_state_worker_control_plane.py` (`14 passed`)
15. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/interfaces/test_cli_startup_semantics.py tests/interfaces/test_sessions_router_protocol_replay.py` (`58 passed`, `4 warnings`)
16. `python -m pytest -q tests/application/test_turn_tool_dispatcher_policy_enforcement.py tests/application/test_turn_tool_dispatcher_compatibility.py` (`13 passed`)
17. `python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_orchestrator_scheduler_control_plane.py tests/platform/test_no_old_namespaces.py` (`21 passed`)
18. `python -m pytest -q tests/contracts/test_control_plane_final_truth_contract.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_packet1.py` (`29 passed`)
19. `python -m pytest -q tests/integration/test_sandbox_terminal_outcome_service.py tests/integration/test_turn_tool_control_plane_closeout.py` (`8 passed`)
20. `python -m pytest -q tests/integration/test_gitea_state_worker_control_plane.py tests/integration/test_sandbox_orchestrator_lifecycle.py` (`17 passed`)

## Remaining blockers or drift

1. `orket/discovery.py` still emits deprecation warnings through the `orket.orket` compatibility shim; removal remains tracked by the future roadmap lane for shim removal.
2. No active ControlPlane implementation queue remains.
