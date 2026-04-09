# ControlPlane Convergence Reopen Implementation Plan
Last updated: 2026-04-09
Status: Active reopened implementation authority
Owner: Orket Core
Lane type: Control-plane convergence reopen / bounded follow-on slices

Paired active requirements authority:
1. `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`
2. `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`

Historical execution records:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CLOSEOUT.md`
3. `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md`

## Authority posture

This document is the active implementation authority for the reopened ControlPlane lane recorded in `docs/ROADMAP.md`.

The accepted packet under `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md` remains the live requirements authority.
The archived `CP04082026-CONVERGENCE-CLOSEOUT` material remains historical execution evidence and must not be edited to carry new active work.

## Why this lane is reopened

The 2026-04-08 closeout truthfully archived a bounded convergence pass, but it also preserved unfinished convergence debt:
1. compatibility exits `CE-01` through `CE-08` remain open
2. the `Workload` crosswalk row still reads `conflicting`
3. the `Run`, `Reservation` / `Lease` / `Resource`, `Effect`, `Checkpoint`, `RecoveryDecision`, `OperatorAction`, `ReconciliationRecord`, and `FinalTruthRecord` rows still remain `partial`
4. the archived plan already named bounded unfinished follow-on slices, so the truthful reopen move is to resume those existing slices instead of inventing a new hidden queue

## Reopen rule

Resume the largest still-bounded unfinished slice queue already defined by the archived convergence plan.

The active queue is:
1. `Slice 2B`
2. `Slice 3B`
3. `Slice 4B`
4. `Slice 5B`
5. `Slice 7B`
6. `Slice 6B`
7. `Slice 8B`

Why this is the next-best queue:
1. `Slice 1A` through `Slice 1F`, `Slice 2A`, `Slice 3A`, `Slice 4A`, `Slice 5A`, `Slice 7A`, `Slice 6A`, and `Slice 8A` are already completed archived context
2. `Slice 2B` is the next unfinished bounded slice in the archived execution order
3. `Slice 7B` still must execute before `Slice 6B`
4. this queue is already proof-shaped, code-surface-bounded, and compatibility-exit-scoped, so it maximizes feasible progress without inventing a larger redesign lane

## Guardrails

1. Do not invent new control-plane nouns.
2. Do not widen beyond the slice queue below without same-change plan updates.
3. Keep the archive truthful: completed slice history stays in the archived closeout packet.
4. If `CE-01` or `CE-02` still remain open after `Slice 8B`, stop and open a fresh bounded follow-on lane instead of silently minting `Slice 1G` or `Slice 1H`.
5. Every slice change must update the crosswalk, the relevant workstream closeout artifact, and `CURRENT_AUTHORITY.md` in the same change.

## Open compatibility exits

1. `CE-01` - workload identity still is not universal across broader runtime start paths
2. `CE-02` - legacy run / attempt / step projection surfaces still can read like authority
3. `CE-03` - shared resource-registry read-side adoption is not yet universal
4. `CE-04` - effect truth still has legacy receipt / summary-backed readbacks
5. `CE-05` - broader resume and restart paths still risk snapshot- or saved-state-led authority
6. `CE-06` - non-sandbox operator and reconciliation authority remains fragmented
7. `CE-07` - final-truth closure still risks summary-backed alternate authority
8. `CE-08` - namespace and capability fail-closed behavior is not yet universal across broader mutation paths

## Active slice queue

### Slice 2B - Shared resource-registry read-side expansion and uncovered ownership-path closure

1. Workstream: 2
2. Crosswalk rows: `Reservation`, `Lease`, `Resource`
3. Exact code surfaces and entrypoints: `orket/application/services/control_plane_target_resource_refs.py`; `orket/application/services/sandbox_lifecycle_view_service.py`; `orket/application/services/kernel_action_control_plane_view_service.py`; `orket/orchestration/approval_control_plane_read_model.py`; `orket/interfaces/coordinator_api.py`; `orket/runtime/execution_pipeline.py`
4. Legacy authority to demote: lease-centric or subsystem-local ownership summaries and uncovered admission or ownership paths that still bypass one shared resource-registry projection
5. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_reservation_contract.py tests/contracts/test_control_plane_lease_contract.py`; `python -m pytest -q tests/interfaces/test_coordinator_api_control_plane.py tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py tests/interfaces/test_api_approvals.py`; `python -m pytest -q tests/integration/test_orchestrator_scheduler_control_plane.py tests/integration/test_gitea_state_worker_control_plane.py tests/application/test_control_plane_target_resource_refs.py`
6. Compatibility exits narrowed or closed: `CE-03`
7. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_2_CLOSEOUT.md`; `CURRENT_AUTHORITY.md`
8. Slice exit condition: touched governed read surfaces and uncovered ownership paths consume one shared resource-registry story, and no touched admission or ownership path relies on lease-only or subsystem-local truth where shared resource truth exists

### Slice 3B - Effect-journal-first closure and remaining legacy read-model demotion

1. Workstream: 3
2. Crosswalk rows: `Effect`, `Run`, `FinalTruthRecord`
3. Exact code surfaces and entrypoints: `workspace/observability/<run_id>/`; `orket/runtime/protocol_receipt_materializer.py`; `orket/runtime/run_summary.py`; `orket/orchestration/approval_control_plane_read_model.py`; `orket/application/services/kernel_action_control_plane_view_service.py`; `orket/application/services/sandbox_lifecycle_view_service.py`
4. Legacy authority to demote: remaining artifact-, receipt-, and summary-backed effect or closure readbacks that still read like primary effect truth instead of effect-journal projections
5. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_effect_journal_contract.py tests/application/test_control_plane_publication_service.py`; `python -m pytest -q tests/runtime/test_protocol_receipt_materializer.py tests/runtime/test_run_summary_packet1.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_artifact_provenance.py`; `python -m pytest -q tests/integration/test_turn_executor_control_plane_evidence.py tests/integration/test_turn_tool_control_plane_closeout.py tests/integration/test_orchestrator_issue_control_plane.py`
6. Compatibility exits narrowed or closed: `CE-04`
7. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_3_CLOSEOUT.md`; `CURRENT_AUTHORITY.md`; and any touched truth-contract doc that still frames artifact or summary output as authority
8. Slice exit condition: every touched legacy effect read surface self-identifies as projection-only with explicit effect-journal source framing, and touched closure or read models consume durable effect history before artifact or receipt evidence

### Slice 4B - Resume authority collapse on remaining snapshot and restart-policy seams

1. Workstream: 4
2. Crosswalk rows: `Checkpoint`, `RecoveryDecision`, `Attempt`
3. Exact code surfaces and entrypoints: `orket/application/services/sandbox_runtime_recovery_service.py`; `orket/application/services/sandbox_restart_policy_service.py`; `orket/application/services/turn_tool_control_plane_recovery.py`; `orket/application/services/turn_tool_control_plane_closeout.py`; `orket/application/review/snapshot_loader.py`; `orket/application/review/models.py`; `orket/runtime/execution_pipeline.py`
4. Legacy authority to demote: snapshot existence, saved-state presence, and service-local restart heuristics that still imply resumability without accepted checkpoint plus recovery-decision truth
5. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_recovery_contract.py tests/application/test_sandbox_control_plane_checkpoint_service.py`; `python -m pytest -q tests/application/test_kernel_action_control_plane_pre_effect_recovery.py tests/integration/test_sandbox_runtime_recovery_service.py`; `python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py`
6. Compatibility exits narrowed or closed: `CE-05`
7. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_4_CLOSEOUT.md`; `CURRENT_AUTHORITY.md` if resume or recovery entrypoint contracts change
8. Slice exit condition: touched resume or recovery paths fail closed unless accepted checkpoint plus explicit recovery-decision truth exists, and snapshot or saved-state presence alone cannot authorize continuation on any touched path

### Slice 5B - Non-sandbox operator and reconciliation publication expansion

1. Workstream: 5
2. Crosswalk rows: `ReconciliationRecord`, `OperatorAction`, `FinalTruthRecord`
3. Exact code surfaces and entrypoints: `orket/interfaces/api.py`; `orket/interfaces/routers/sessions.py`; `orket/interfaces/routers/approvals.py`; `orket/interfaces/routers/kernel.py`; `orket/orchestration/approval_control_plane_read_model.py`; `orket/runtime/operator_override_logging_policy.py`; `orket/orchestration/engine.py`; `orket/orchestration/engine_approvals.py`; `orket/application/workflows/orchestrator.py`; `orket/application/workflows/orchestrator_ops.py`
4. Legacy authority to demote: endpoint-local, log-local, and non-sandbox operator or divergence behavior that still acts as hidden control-plane authority outside the recorded sandbox, approval, governed turn, governed kernel, and Gitea slices
5. Required proof commands: `python -m pytest -q tests/interfaces/test_api_nervous_system_operator_surfaces.py tests/application/test_tool_approval_control_plane_operator_service.py`; `python -m pytest -q tests/application/test_pending_gate_control_plane_operator_service.py tests/application/test_kernel_action_control_plane_operator_service.py`; `python -m pytest -q tests/integration/test_sandbox_lifecycle_reconciliation_service.py tests/integration/test_gitea_state_worker_control_plane.py`
6. Compatibility exits narrowed or closed: `CE-06`
7. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_5_CLOSEOUT.md`; `CURRENT_AUTHORITY.md`
8. Slice exit condition: touched operator and reconciliation paths publish through one first-class record family, and read models preserve command versus risk-acceptance versus attestation split explicitly across the touched non-sandbox surfaces

### Slice 7B - Namespace and capability fail-closed expansion on remaining governed mutation paths

1. Workstream: 7
2. Crosswalk rows: `Workload`, `Resource`, `Reservation`, `Lease`, `Effect`
3. Exact code surfaces and entrypoints: `orket/application/workflows/turn_tool_dispatcher.py`; `orket/application/services/turn_tool_control_plane_resource_lifecycle.py`; `orket/application/services/turn_tool_control_plane_service.py`; `orket/application/services/control_plane_workload_catalog.py`; `orket/application/services/orchestrator_issue_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`; `orket/application/workflows/turn_executor_control_plane.py`; `orket/interfaces/api.py`; `orket/interfaces/routers/kernel.py`; `orket/orchestration/engine.py`
4. Legacy authority to demote: ambient namespace visibility, undeclared capability scope, and journal-free mutation on broader runtime workloads and scheduling beyond the recorded governed turn-tool and scheduler-owned mutation slices
5. Required proof commands: `python -m pytest -q tests/application/test_turn_tool_dispatcher_policy_enforcement.py tests/application/test_turn_tool_dispatcher_compatibility.py`; `python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_orchestrator_scheduler_control_plane.py`; `python -m pytest -q tests/platform/test_no_old_namespaces.py`
6. Compatibility exits narrowed or closed: `CE-08`
7. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_7_CLOSEOUT.md`; `CURRENT_AUTHORITY.md`; `docs/specs/WORKLOAD_CONTRACT_V1.md` if workload or namespace contract framing changes materially
8. Slice exit condition: touched mutation paths fail closed on undeclared namespace or capability scope, and broader workload composition preserves explicit namespace inheritance or override rules instead of ambient access

### Slice 6B - Remaining terminal closeout fail-closed final-truth gating

1. Workstream: 6
2. Crosswalk rows: `FinalTruthRecord`, `Run`, `Effect`, `OperatorAction`, `ReconciliationRecord`
3. Exact code surfaces and entrypoints: `orket/core/domain/control_plane_final_truth.py`; `orket/application/services/sandbox_control_plane_closure_service.py`; `orket/application/services/sandbox_terminal_outcome_service.py`; `orket/application/services/kernel_action_control_plane_service.py`; `orket/application/services/turn_tool_control_plane_service.py`; `orket/application/services/gitea_state_control_plane_execution_service.py`; `orket/runtime/run_summary.py`; `orket/runtime/runtime_truth_contracts.py`; `orket/runtime/execution_pipeline.py`
4. Legacy authority to demote: surviving summary-backed or packet-1-style closeout surfaces and terminal paths that can still succeed without published final truth
5. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_final_truth_contract.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_packet1.py`; `python -m pytest -q tests/integration/test_sandbox_terminal_outcome_service.py tests/integration/test_turn_tool_control_plane_closeout.py`; `python -m pytest -q tests/integration/test_gitea_state_worker_control_plane.py tests/integration/test_sandbox_orchestrator_lifecycle.py`
6. Compatibility exits narrowed or closed: `CE-07`
7. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_6_CLOSEOUT.md`; `CURRENT_AUTHORITY.md`; `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` if any surviving projection contract remains
8. Slice exit condition: every touched terminal path emits `FinalTruthRecord` before successful closeout, and no touched legacy summary surface authors terminal truth instead of projecting it

### Slice 8B - Lane-wide closeout synchronization after the follow-on convergence cuts

1. Workstream: 8
2. Crosswalk rows: any row changed by the converged code slices in the same batch
3. Exact doc surfaces: `docs/ROADMAP.md`; `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`; `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/CLOSEOUT.md`; this plan; `CURRENT_AUTHORITY.md`; and the touched workstream closeout artifacts
4. Legacy authority to demote: stale queue wording, contradictory compatibility-exit posture, or closeout claims that drift away from the re-verified recorded slices plus the follow-on cuts
5. Required proof commands: `python scripts/governance/check_docs_project_hygiene.py`; `python -m pytest -q tests/platform/test_current_authority_map.py tests/platform/test_no_old_namespaces.py`
6. Compatibility exits narrowed or closed: whichever exit ids the paired code slices truthfully narrow or close; never claim a close without updating the ledger and the relevant closeout artifact in the same change
7. Same-change doc updates: roadmap, packet README, crosswalk, this plan, `CURRENT_AUTHORITY.md`, and the relevant workstream closeout artifacts whenever lane status, crosswalk status, or compatibility-exit posture changes
8. Slice exit condition: touched docs, code, proofs, compatibility exits, and closeout claims tell one authority story, and no open queue points at already-green recorded slices

## Completion boundary

This reopened lane is complete only when:
1. `Slice 2B` through `Slice 8B` are either completed or truthfully retired in same-change authority updates
2. the roadmap, this plan, the packet README, `CURRENT_AUTHORITY.md`, and the touched workstream closeout artifacts all tell the same active-lane story
3. any residual `CE-01` / `CE-02` drift that survives this queue is split into a new bounded follow-on lane instead of being hidden inside this reopen
