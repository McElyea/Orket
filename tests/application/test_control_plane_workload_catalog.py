# Layer: unit

from __future__ import annotations

from orket.application.services.control_plane_workload_catalog import (
    CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    GITEA_STATE_WORKER_EXECUTION_WORKLOAD,
    KERNEL_ACTION_WORKLOAD,
    ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD,
    ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD,
    ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD,
    REVIEW_RUN_WORKLOAD,
    SANDBOX_RUNTIME_WORKLOAD_VERSION,
    TURN_TOOL_WORKLOAD,
    governed_control_plane_workloads,
    sandbox_runtime_workload_for_tech_stack,
)
from orket.application.services.gitea_state_control_plane_execution_service import (
    GiteaStateControlPlaneExecutionService,
)
from orket.application.services.kernel_action_control_plane_service import (
    KernelActionControlPlaneService,
)
from orket.application.services.orchestrator_issue_control_plane_service import (
    OrchestratorIssueControlPlaneService,
)
from orket.application.services.orchestrator_scheduler_control_plane_service import (
    OrchestratorSchedulerControlPlaneService,
)
from orket.application.services.sandbox_control_plane_execution_service import (
    SandboxControlPlaneExecutionService,
)
from orket.application.services.turn_tool_control_plane_service import (
    TurnToolControlPlaneService,
)
from orket.domain.sandbox import TechStack


def test_governed_control_plane_workload_catalog_exposes_stable_workload_records() -> None:
    workloads = governed_control_plane_workloads()

    assert workloads[:6] == (
        KERNEL_ACTION_WORKLOAD,
        ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD,
        ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD,
        ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD,
        TURN_TOOL_WORKLOAD,
        GITEA_STATE_WORKER_EXECUTION_WORKLOAD,
    )
    assert workloads[6] == REVIEW_RUN_WORKLOAD
    assert len(workloads) == 12
    assert all(record.output_contract_ref == CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF for record in workloads)
    assert all(record.workload_digest.startswith("sha256:") for record in workloads)
    assert sandbox_runtime_workload_for_tech_stack("fastapi-react-postgres") in workloads


def test_sandbox_runtime_workload_catalog_resolves_supported_tech_stacks() -> None:
    workload = sandbox_runtime_workload_for_tech_stack(TechStack.FASTAPI_REACT_POSTGRES)

    assert workload.workload_id == "sandbox-workload:fastapi-react-postgres"
    assert workload.workload_version == SANDBOX_RUNTIME_WORKLOAD_VERSION
    assert workload.output_contract_ref == CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF
    assert workload.workload_digest.startswith("sha256:")


def test_governed_control_plane_services_alias_the_shared_workload_catalog() -> None:
    assert KernelActionControlPlaneService.WORKLOAD == KERNEL_ACTION_WORKLOAD
    assert OrchestratorIssueControlPlaneService.WORKLOAD == ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD
    assert OrchestratorSchedulerControlPlaneService.TRANSITION_WORKLOAD == ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD
    assert (
        OrchestratorSchedulerControlPlaneService.CHILD_WORKLOAD
        == ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD
    )
    assert TurnToolControlPlaneService.WORKLOAD == TURN_TOOL_WORKLOAD
    assert GiteaStateControlPlaneExecutionService.WORKLOAD == GITEA_STATE_WORKER_EXECUTION_WORKLOAD
    assert SandboxControlPlaneExecutionService is not None
