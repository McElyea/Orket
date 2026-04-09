# ControlPlane Convergence Reopen Closeout

Last updated: 2026-04-09
Status: Completed
Owner: Orket Core

Archived lane authority:
1. `docs/projects/archive/ControlPlane/CP04092026-CONVERGENCE-REOPEN-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_REOPEN_IMPLEMENTATION_PLAN.md`

Historical context:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CLOSEOUT.md`
2. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_1_CLOSEOUT.md`
3. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_2_CLOSEOUT.md`
4. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_3_CLOSEOUT.md`
5. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_4_CLOSEOUT.md`
6. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_5_CLOSEOUT.md`
7. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_6_CLOSEOUT.md`
8. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_7_CLOSEOUT.md`
9. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_8_CLOSEOUT.md`

## Outcome

The bounded 2026-04-09 convergence reopen is closed.

Closeout facts:
1. the queued follow-on proof set for `Slice 2B`, `Slice 3B`, `Slice 4B`, `Slice 5B`, `Slice 7B`, `Slice 6B`, and `Slice 8B` stayed green on `2026-04-09` without requiring additional runtime code changes
2. the completed reopen closes `CE-03`, `CE-04`, `CE-05`, `CE-06`, `CE-07`, and `CE-08` for the converged resource, effect, recovery, reconciliation/operator, final-truth, and namespace surfaces exercised by that queue
3. at the time of this reopen closeout, residual `CE-01` and `CE-02` drift moved into a fresh bounded follow-on lane; that residual lane is now archived at `docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/`, while the durable Workstream 1 governance companion now lives at `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`
4. the accepted control-plane packet under `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md` remains the active requirements authority and current-state honesty set

## Verification

Proof type: `structural`
Observed path: `primary`
Observed result: `success`

Executed proof:
1. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/contracts/test_control_plane_reservation_contract.py tests/contracts/test_control_plane_lease_contract.py` (`20 passed`)
2. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/interfaces/test_coordinator_api_control_plane.py tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py tests/interfaces/test_api_approvals.py` (`21 passed`)
3. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/integration/test_orchestrator_scheduler_control_plane.py tests/integration/test_gitea_state_worker_control_plane.py tests/application/test_control_plane_target_resource_refs.py` (`15 passed`)
4. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/contracts/test_control_plane_effect_journal_contract.py tests/application/test_control_plane_publication_service.py` (`20 passed`)
5. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_protocol_receipt_materializer.py tests/runtime/test_run_summary_packet1.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_artifact_provenance.py` (`27 passed`)
6. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/integration/test_turn_executor_control_plane_evidence.py tests/integration/test_turn_tool_control_plane_closeout.py tests/integration/test_orchestrator_issue_control_plane.py` (`14 passed`)
7. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/contracts/test_control_plane_recovery_contract.py tests/application/test_sandbox_control_plane_checkpoint_service.py` (`13 passed`)
8. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_kernel_action_control_plane_pre_effect_recovery.py tests/integration/test_sandbox_runtime_recovery_service.py` (`13 passed`)
9. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py` (`16 passed`)
10. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/interfaces/test_api_nervous_system_operator_surfaces.py tests/application/test_tool_approval_control_plane_operator_service.py` (`8 passed`)
11. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_pending_gate_control_plane_operator_service.py tests/application/test_kernel_action_control_plane_operator_service.py` (`4 passed`)
12. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/integration/test_sandbox_lifecycle_reconciliation_service.py tests/integration/test_gitea_state_worker_control_plane.py` (`14 passed`)
13. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_turn_tool_dispatcher_policy_enforcement.py tests/application/test_turn_tool_dispatcher_compatibility.py` (`13 passed`)
14. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_orchestrator_scheduler_control_plane.py` (`19 passed`)
15. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/platform/test_no_old_namespaces.py` (`2 passed`)
16. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/contracts/test_control_plane_final_truth_contract.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_packet1.py` (`29 passed`)
17. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/integration/test_sandbox_terminal_outcome_service.py tests/integration/test_turn_tool_control_plane_closeout.py` (`8 passed`)
18. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/integration/test_gitea_state_worker_control_plane.py tests/integration/test_sandbox_orchestrator_lifecycle.py` (`17 passed`)
19. `python scripts/governance/check_docs_project_hygiene.py` (pass)
20. `python -m pytest -q tests/platform/test_current_authority_map.py tests/platform/test_no_old_namespaces.py`

## Remaining blockers or drift

1. `CE-01` and `CE-02` remained open at the moment of this reopen closeout, but later closed through `docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/`.
2. The `Workload` row read `conflicting` and the `Run` row read `partial` at the moment of this reopen closeout; the active current-state crosswalk has since been synchronized.
3. New active ControlPlane implementation work now reopens explicitly through `docs/ROADMAP.md` instead of this archived reopen queue.
