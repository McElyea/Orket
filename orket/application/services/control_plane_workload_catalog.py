from __future__ import annotations

from orket.core.contracts import WorkloadRecord, build_control_plane_workload_record
from orket.core.domain import CapabilityClass


CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF = "control_plane.contract.v1:RunRecord"
SANDBOX_RUNTIME_WORKLOAD_VERSION = "docker_sandbox_runtime.v1"
_SUPPORTED_SANDBOX_TECH_STACKS = (
    "fastapi-react-postgres",
    "fastapi-vue-mongo",
    "csharp-razor-ef",
    "node-react-postgres",
    "django-react-postgres",
)

KERNEL_ACTION_WORKLOAD = build_control_plane_workload_record(
    workload_id="kernel-action-path",
    workload_version="kernel_api.v1",
    input_contract_ref="kernel_api/v1",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
)

ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD = build_control_plane_workload_record(
    workload_id="orchestrator-issue-dispatch",
    workload_version="orchestrator.issue_dispatch.v1",
    input_contract_ref="orchestrator.issue_dispatch.transition",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    declared_capabilities=[CapabilityClass.BOUNDED_LOCAL_MUTATION],
)

ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD = build_control_plane_workload_record(
    workload_id="orchestrator-issue-scheduler",
    workload_version="orchestrator.issue_scheduler.v1",
    input_contract_ref="orchestrator.issue_scheduler.transition",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    declared_capabilities=[CapabilityClass.BOUNDED_LOCAL_MUTATION],
)

ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD = build_control_plane_workload_record(
    workload_id="orchestrator-child-workload-composition",
    workload_version="orchestrator.child_workload_composition.v1",
    input_contract_ref="orchestrator.child_workload_composition.issue_creation",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    declared_capabilities=[CapabilityClass.BOUNDED_LOCAL_MUTATION],
)

TURN_TOOL_WORKLOAD = build_control_plane_workload_record(
    workload_id="governed-turn-tools",
    workload_version="turn_executor.governed.v1",
    input_contract_ref="turn_executor.governed.input.v1",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
)

GITEA_STATE_WORKER_EXECUTION_WORKLOAD = build_control_plane_workload_record(
    workload_id="gitea-state-worker-card-execution",
    workload_version="gitea_state_worker.v1",
    input_contract_ref="gitea.state_backend.claimed_card.v1",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    declared_capabilities=[CapabilityClass.EXTERNAL_MUTATION],
)

REVIEW_RUN_WORKLOAD = build_control_plane_workload_record(
    workload_id="review-run-manual",
    workload_version="review_run.v0",
    input_contract_ref="docs/specs/REVIEW_RUN_V0.md",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    declared_capabilities=[CapabilityClass.DETERMINISTIC_COMPUTE],
)

_SANDBOX_RUNTIME_WORKLOADS = {
    tech_stack: build_control_plane_workload_record(
        workload_id=f"sandbox-workload:{tech_stack}",
        workload_version=SANDBOX_RUNTIME_WORKLOAD_VERSION,
        input_contract_ref="sandbox.lifecycle.create.v1",
        output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
        declared_capabilities=[CapabilityClass.EXTERNAL_MUTATION],
        declared_resource_classes=[
            "docker_compose_project",
            "docker_container",
            "docker_network",
            "docker_volume",
        ],
        recovery_policy_refs=["docker_sandbox_lifecycle.v1"],
        reconciliation_requirements=["sandbox_runtime_absence_requires_reconciliation"],
        definition_payload={"tech_stack": tech_stack},
    )
    for tech_stack in _SUPPORTED_SANDBOX_TECH_STACKS
}


def sandbox_runtime_workload_for_tech_stack(tech_stack: object) -> WorkloadRecord:
    normalized = str(getattr(tech_stack, "value", tech_stack) or "").strip().lower()
    workload = _SANDBOX_RUNTIME_WORKLOADS.get(normalized)
    if workload is None:
        supported = ", ".join(_SUPPORTED_SANDBOX_TECH_STACKS)
        raise ValueError(f"unsupported sandbox tech_stack={normalized!r}; expected one of {supported}")
    return workload


def governed_control_plane_workloads() -> tuple[WorkloadRecord, ...]:
    return (
        KERNEL_ACTION_WORKLOAD,
        ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD,
        ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD,
        ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD,
        TURN_TOOL_WORKLOAD,
        GITEA_STATE_WORKER_EXECUTION_WORKLOAD,
        REVIEW_RUN_WORKLOAD,
        *_SANDBOX_RUNTIME_WORKLOADS.values(),
    )


__all__ = [
    "CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF",
    "GITEA_STATE_WORKER_EXECUTION_WORKLOAD",
    "KERNEL_ACTION_WORKLOAD",
    "ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD",
    "ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD",
    "ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD",
    "REVIEW_RUN_WORKLOAD",
    "SANDBOX_RUNTIME_WORKLOAD_VERSION",
    "TURN_TOOL_WORKLOAD",
    "governed_control_plane_workloads",
    "sandbox_runtime_workload_for_tech_stack",
]
