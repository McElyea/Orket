# ControlPlane Project Closeout Readiness Implementation Plan
Last updated: 2026-04-09
Status: Active implementation authority
Owner: Orket Core
Lane type: ControlPlane project completion / closeout-readiness follow-on

Paired active requirements authority:
1. `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`
2. `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
3. `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`

Historical execution records:
1. `docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/`
2. `docs/projects/archive/ControlPlane/CP04092026-CONVERGENCE-REOPEN-CLOSEOUT/`
3. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/`
4. `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/`

## Purpose

Truthfully assess whether `docs/projects/ControlPlane/` can close out, separate ready-now work from later-only closeout tasks, and drive the remaining packet backlog without reopening already-closed slices as if they were still the active queue.

## Closeout assessment

`docs/projects/ControlPlane/` cannot close out yet.

Reasons:
1. the live crosswalk still marks `Workload`, `Run`, `Attempt`, `Step`, `Effect`, `Resource`, `Reservation`, `Lease`, `Checkpoint`, `RecoveryDecision`, `ReconciliationRecord`, `OperatorAction`, and `FinalTruthRecord` as `partial`
2. the live weakest-area assessment still shows open backlog in reservation coverage, lease/resource read-side coverage, operator-action publication, effect-journal authority, checkpoint defaulting, and broader namespace authority
3. active implementation and projection-lock authority still remain under `docs/projects/ControlPlane/`, so the project is not archive-ready even after spec extraction

No external blocker currently prevents execution of the ready-now queue below.

## Completed in this lane

### Slice CP0 - Packet spec extraction and closeout-readiness relink

Completed on `2026-04-09`.

Outcome:
1. durable glossary and requirement authority now lives under `docs/specs/` and is indexed by `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`
2. legacy project-local packet requirement paths now survive only as compatibility redirects
3. roadmap, current-authority, and packet companion docs no longer treat the project folder as the canonical requirement home

## Ready-now queue

### Slice CP1 - Broader reservation / lease / resource authority universalization

1. Crosswalk rows: `Reservation`, `Lease`, `Resource`
2. Exact code surfaces and entrypoints: `orket/application/services/control_plane_target_resource_refs.py`; `orket/application/services/sandbox_lifecycle_view_service.py`; `orket/application/services/kernel_action_control_plane_view_service.py`; `orket/orchestration/approval_control_plane_read_model.py`; `orket/interfaces/coordinator_api.py`; `orket/runtime/execution_pipeline.py`; `orket/application/services/orchestrator_issue_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_service.py`; `orket/application/services/gitea_state_worker.py`
3. Legacy authority to demote: lease-centric or subsystem-local ownership summaries and admission or scheduling paths that still bypass shared reservation/resource truth
4. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_reservation_contract.py tests/contracts/test_control_plane_lease_contract.py`; `python -m pytest -q tests/interfaces/test_coordinator_api_control_plane.py tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py tests/interfaces/test_api_approvals.py`; `python -m pytest -q tests/integration/test_orchestrator_scheduler_control_plane.py tests/integration/test_gitea_state_worker_control_plane.py tests/application/test_control_plane_target_resource_refs.py`
5. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `CURRENT_AUTHORITY.md`; this plan
6. Slice exit condition: touched governed read surfaces and uncovered admission or ownership paths consume one shared resource-registry story, and touched admission or scheduling paths no longer omit reservation truth where the packet requires it

### Slice CP2 - Broader effect-journal-first read-side and artifact demotion

1. Crosswalk rows: `Effect`, `Run`, `FinalTruthRecord`
2. Exact code surfaces and entrypoints: `workspace/observability/<run_id>/`; `orket/runtime/protocol_receipt_materializer.py`; `orket/runtime/run_summary.py`; `orket/runtime/run_summary_packet2.py`; `orket/runtime/run_summary_artifact_provenance.py`; `scripts/common/run_summary_support.py`; `orket/orchestration/approval_control_plane_read_model.py`; `orket/application/services/kernel_action_control_plane_view_service.py`; `orket/application/services/sandbox_lifecycle_view_service.py`
3. Legacy authority to demote: artifact-, receipt-, and summary-backed effect or closure readbacks that still read like primary effect truth instead of effect-journal projections
4. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_effect_journal_contract.py tests/application/test_control_plane_publication_service.py`; `python -m pytest -q tests/runtime/test_protocol_receipt_materializer.py tests/runtime/test_run_summary_packet1.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_artifact_provenance.py tests/scripts/test_common_run_summary_support.py`; `python -m pytest -q tests/integration/test_turn_executor_control_plane_evidence.py tests/integration/test_turn_tool_control_plane_closeout.py tests/integration/test_orchestrator_issue_control_plane.py`
5. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `CURRENT_AUTHORITY.md`; this plan; and any touched truth-contract doc that still frames artifact or summary output as authority
6. Slice exit condition: every touched effect or closure read surface self-identifies as projection-only with explicit effect-journal source framing, and touched closure or read models consume durable effect history before artifact or receipt evidence

### Slice CP3 - Broader checkpoint / recovery authority universalization

1. Crosswalk rows: `Checkpoint`, `RecoveryDecision`, `Attempt`
2. Exact code surfaces and entrypoints: `orket/application/services/sandbox_runtime_recovery_service.py`; `orket/application/services/sandbox_restart_policy_service.py`; `orket/application/services/turn_tool_control_plane_recovery.py`; `orket/application/services/turn_tool_control_plane_closeout.py`; `orket/application/services/gitea_state_control_plane_execution_service.py`; `orket/application/review/snapshot_loader.py`; `orket/application/review/models.py`; `orket/runtime/execution_pipeline.py`
3. Legacy authority to demote: snapshot existence, saved-state presence, and service-local restart heuristics that still imply resumability without accepted checkpoint plus recovery-decision truth
4. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_recovery_contract.py tests/application/test_sandbox_control_plane_checkpoint_service.py`; `python -m pytest -q tests/application/test_kernel_action_control_plane_pre_effect_recovery.py tests/integration/test_sandbox_runtime_recovery_service.py`; `python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py`
5. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `CURRENT_AUTHORITY.md`; this plan
6. Slice exit condition: touched resume or recovery paths fail closed unless accepted checkpoint plus explicit recovery-decision truth exists, and snapshot or saved-state presence alone cannot authorize continuation on any touched path

### Slice CP4 - Broader reconciliation / operator-action universalization

1. Crosswalk rows: `ReconciliationRecord`, `OperatorAction`, `FinalTruthRecord`
2. Exact code surfaces and entrypoints: `orket/interfaces/api.py`; `orket/interfaces/routers/sessions.py`; `orket/interfaces/routers/approvals.py`; `orket/interfaces/routers/kernel.py`; `orket/orchestration/approval_control_plane_read_model.py`; `orket/runtime/operator_override_logging_policy.py`; `orket/orchestration/engine.py`; `orket/orchestration/engine_approvals.py`; `orket/application/workflows/orchestrator.py`; `orket/application/workflows/orchestrator_ops.py`
3. Legacy authority to demote: endpoint-local, log-local, and non-sandbox operator or divergence behavior that still acts as hidden control-plane authority outside the covered sandbox, approval, governed-turn, governed-kernel, and Gitea paths
4. Required proof commands: `python -m pytest -q tests/interfaces/test_api_nervous_system_operator_surfaces.py tests/application/test_tool_approval_control_plane_operator_service.py`; `python -m pytest -q tests/application/test_pending_gate_control_plane_operator_service.py tests/application/test_kernel_action_control_plane_operator_service.py`; `python -m pytest -q tests/integration/test_sandbox_lifecycle_reconciliation_service.py tests/integration/test_gitea_state_worker_control_plane.py`
5. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `CURRENT_AUTHORITY.md`; this plan
6. Slice exit condition: touched operator and reconciliation paths publish through one first-class record family, and read models preserve command versus risk-acceptance versus attestation split explicitly across the touched non-sandbox surfaces

### Slice CP5 - Broader workload / namespace / safe-tooling universalization

1. Crosswalk rows: `Workload`, `Reservation`, `Lease`, `Resource`, `Effect`
2. Exact code surfaces and entrypoints: `orket/application/services/control_plane_workload_catalog.py`; `orket/extensions/catalog.py`; `orket/extensions/manager.py`; `orket/interfaces/cli.py`; `orket/interfaces/routers/sessions.py`; `scripts/odr/run_arbiter.py`; `orket/application/workflows/turn_tool_dispatcher.py`; `orket/application/services/turn_tool_control_plane_resource_lifecycle.py`; `orket/application/services/turn_tool_control_plane_service.py`; `orket/application/services/orchestrator_issue_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`; `orket/application/workflows/turn_executor_control_plane.py`; `orket/interfaces/api.py`; `orket/interfaces/routers/kernel.py`; `orket/orchestration/engine.py`
3. Legacy authority to demote: ambient namespace visibility, undeclared capability scope, extension-manifest-facing start-path drift, and journal-free mutation on broader runtime workloads and scheduling beyond the already-closed governed start-path and scheduler slices
4. Required proof commands: `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/interfaces/test_cli_startup_semantics.py tests/interfaces/test_sessions_router_protocol_replay.py`; `python -m pytest -q tests/application/test_turn_tool_dispatcher_policy_enforcement.py tests/application/test_turn_tool_dispatcher_compatibility.py`; `python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_orchestrator_scheduler_control_plane.py`; `python -m pytest -q tests/platform/test_no_old_namespaces.py`
5. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md` if the governed start-path matrix changes; `CURRENT_AUTHORITY.md`; this plan; `docs/specs/WORKLOAD_CONTRACT_V1.md` if workload or namespace contract framing changes materially
6. Slice exit condition: broader workload starts, workload composition, and governed mutation paths fail closed on undeclared namespace or capability scope, and the live workload/start-path matrix remains truthful for any newly-admitted consumer

### Slice CP6 - Broader final-truth closure gating and projection demotion

1. Crosswalk rows: `FinalTruthRecord`, `Run`, `Effect`, `OperatorAction`, `ReconciliationRecord`
2. Exact code surfaces and entrypoints: `orket/core/domain/control_plane_final_truth.py`; `orket/application/services/sandbox_control_plane_closure_service.py`; `orket/application/services/sandbox_terminal_outcome_service.py`; `orket/application/services/kernel_action_control_plane_service.py`; `orket/application/services/turn_tool_control_plane_service.py`; `orket/application/services/gitea_state_control_plane_execution_service.py`; `orket/runtime/run_summary.py`; `orket/runtime/runtime_truth_contracts.py`; `orket/runtime/execution_pipeline.py`
3. Legacy authority to demote: surviving summary-backed or packet-1-style closeout surfaces and terminal paths that can still succeed without published final truth
4. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_final_truth_contract.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_packet1.py`; `python -m pytest -q tests/integration/test_sandbox_terminal_outcome_service.py tests/integration/test_turn_tool_control_plane_closeout.py`; `python -m pytest -q tests/integration/test_gitea_state_worker_control_plane.py tests/integration/test_sandbox_orchestrator_lifecycle.py`
5. Same-change doc updates: `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `CURRENT_AUTHORITY.md`; this plan; `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` if any surviving projection contract remains
6. Slice exit condition: every touched terminal path emits `FinalTruthRecord` before successful closeout, and no touched legacy summary surface authors terminal truth instead of projecting it

### Slice CP7 - ControlPlane project closeout and archive

1. Crosswalk rows: every row that still participates in the active closeout claim
2. Exact doc surfaces: `docs/ROADMAP.md`; `CURRENT_AUTHORITY.md`; `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`; `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`; `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00_CONTROL_PLANE_FOUNDATION_PACKET.md`; `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/09_OS_MASTER_PLAN.md`; `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`; this plan; and the resulting archive target under `docs/projects/archive/ControlPlane/`
3. Legacy authority to demote: the active `docs/projects/ControlPlane/` folder as the home of live ControlPlane requirement or implementation authority
4. Required proof commands: `python scripts/governance/check_docs_project_hygiene.py`; `python -m pytest -q tests/platform/test_current_authority_map.py tests/platform/test_no_old_namespaces.py`
5. Same-change doc updates: roadmap, project index, current authority, spec index, packet README, foundation packet, OS master plan, this plan, and the resulting closeout/archive docs
6. Slice exit condition: durable ControlPlane contract authority no longer depends on `docs/projects/ControlPlane/`, the remaining project-local docs are either archived or explicitly reduced to non-project durable homes, and the roadmap no longer needs an active ControlPlane lane

## Later-only boundary

The following work must wait until the ready-now queue above has been executed:
1. archival closeout of `docs/projects/ControlPlane/` must wait until `CP1` through `CP6` are complete and the project folder no longer carries unresolved packet-row drift or active non-archive implementation authority
2. any richer namespace hierarchy, distributed-control-plane, or product-surface redesign beyond the accepted packet remains out of scope for this follow-on lane and must reopen only with an explicit new request

## Completion boundary

This follow-on lane is complete only when:
1. `CP1` through `CP7` are either completed or truthfully retired in same-change authority updates, with `CP0` remaining complete
2. the roadmap, project index, current-authority snapshot, spec index, packet README, Workstream 1 companion, and archive posture all tell the same story
3. no active ControlPlane requirement or implementation authority still depends on `docs/projects/ControlPlane/`
