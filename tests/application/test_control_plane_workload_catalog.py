# Layer: unit

from __future__ import annotations

from pathlib import Path

from orket.application.services.control_plane_workload_catalog import (
    CARDS_CONTROL_PLANE_WORKLOAD_ID,
    CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    GITEA_STATE_WORKER_EXECUTION_WORKLOAD,
    KERNEL_ACTION_WORKLOAD,
    ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD,
    ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD,
    ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD,
    REVIEW_RUN_WORKLOAD,
    SANDBOX_RUNTIME_WORKLOAD_VERSION,
    TURN_TOOL_WORKLOAD,
    _resolve_cards_control_plane_workload_from_contract,
    _resolve_extension_control_plane_workload,
    _resolve_odr_arbiter_control_plane_workload_from_contract,
    WorkloadAuthorityInput,
    build_cards_workload_contract,
    control_plane_workload_for_key,
    governed_control_plane_workloads,
    resolve_control_plane_workload,
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
from orket.core.contracts import WORKLOAD_CONTRACT_VERSION_V1, parse_workload_contract
from orket.domain.sandbox import TechStack
from orket.schema import ArchitectureGovernance, EpicConfig, IssueConfig


def _epic() -> EpicConfig:
    return EpicConfig(
        id="epic-1",
        name="epic-1",
        type="epic",
        team="standard",
        environment="standard",
        description="catalog test",
        architecture_governance=ArchitectureGovernance(idesign=False, pattern="Standard"),
        issues=[
            IssueConfig(id="ISSUE-1", summary="A", seat="lead_architect", priority="High", depends_on=[]),
            IssueConfig(id="ISSUE-2", summary="B", seat="lead_architect", priority="Medium", depends_on=["ISSUE-1"]),
        ],
    )


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


def test_workload_authority_resolver_supports_catalog_and_contract_modes(tmp_path: Path) -> None:
    assert control_plane_workload_for_key("kernel_action") == KERNEL_ACTION_WORKLOAD
    assert (
        resolve_control_plane_workload(
            WorkloadAuthorityInput(
                kind="catalog_workload",
                workload_key="sandbox-workload:fastapi-react-postgres",
            )
        )
        == sandbox_runtime_workload_for_tech_stack("fastapi-react-postgres")
    )

    contract_payload = build_cards_workload_contract(
        epic=_epic(),
        run_id="sess-2",
        build_id="build-2",
        workspace=tmp_path,
        department="core",
    )
    record = resolve_control_plane_workload(
        WorkloadAuthorityInput(
            kind="workload_contract_v1",
            workload_id=CARDS_CONTROL_PLANE_WORKLOAD_ID,
            contract_payload=contract_payload,
            output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
            definition_payload={"department": "core"},
        )
    )

    assert record.workload_id == CARDS_CONTROL_PLANE_WORKLOAD_ID
    assert record.workload_version == WORKLOAD_CONTRACT_VERSION_V1


def test_cards_workload_builders_route_through_shared_catalog(tmp_path: Path) -> None:
    """Layer: unit. Verifies cards workload contract building and authority resolution now live only on the shared catalog."""
    contract_payload = build_cards_workload_contract(
        epic=_epic(),
        run_id="sess-1",
        build_id="build-1",
        workspace=tmp_path,
        department="core",
    )

    assert parse_workload_contract(contract_payload).workload_contract_version == WORKLOAD_CONTRACT_VERSION_V1

    record = resolve_control_plane_workload(
        WorkloadAuthorityInput(
            kind="workload_contract_v1",
            workload_id=CARDS_CONTROL_PLANE_WORKLOAD_ID,
            contract_payload=contract_payload,
            output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
            definition_payload={"department": "core"},
        )
    )

    assert record.workload_id == CARDS_CONTROL_PLANE_WORKLOAD_ID
    assert record.workload_version == WORKLOAD_CONTRACT_VERSION_V1
    assert record.output_contract_ref == CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF
    assert record.input_contract_ref == "docs/specs/WORKLOAD_CONTRACT_V1.md"
    assert record.workload_digest.startswith("sha256:")


def test_cards_workload_record_helper_keeps_runtime_entrypoints_out_of_authority_input_shape(tmp_path: Path) -> None:
    """Layer: unit. Verifies cards runtime entrypoints can resolve their workload record through one catalog-local helper."""
    contract_payload = build_cards_workload_contract(
        epic=_epic(),
        run_id="sess-3",
        build_id="build-3",
        workspace=tmp_path,
        department="core",
    )

    record = _resolve_cards_control_plane_workload_from_contract(
        contract_payload=contract_payload,
        department="core",
    )

    assert record.workload_id == CARDS_CONTROL_PLANE_WORKLOAD_ID
    assert record.workload_version == WORKLOAD_CONTRACT_VERSION_V1
    assert record.output_contract_ref == CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF
    assert record.workload_digest.startswith("sha256:")


def test_extension_manifest_workload_projection_uses_shared_builder() -> None:
    record = resolve_control_plane_workload(
        WorkloadAuthorityInput(
            kind="extension_manifest_workload",
            workload_id="demo_v1",
            workload_version="1.0.0",
            extension_id="demo.ext",
            extension_version="1.2.3",
            entrypoint="demo:run",
            required_capabilities=("workspace.root",),
            contract_style="sdk_v0",
            manifest_digest_sha256="f" * 64,
        )
    )

    assert record.workload_id == "demo_v1"
    assert record.input_contract_ref == "extension_manifest:sdk_v0"
    assert record.output_contract_ref == "extension_run_result_identity_v1"
    assert record.workload_digest.startswith("sha256:")


def test_extension_workload_record_helper_keeps_manager_out_of_authority_input_shape() -> None:
    """Layer: unit. Verifies extension workload start can resolve one workload record through a catalog-local helper."""
    record = _resolve_extension_control_plane_workload(
        workload_id="demo_v1",
        workload_version="1.0.0",
        extension_id="demo.ext",
        extension_version="1.2.3",
        entrypoint="demo:run",
        required_capabilities=("workspace.root",),
        contract_style="sdk_v0",
        manifest_digest_sha256="f" * 64,
    )

    assert record.workload_id == "demo_v1"
    assert record.input_contract_ref == "extension_manifest:sdk_v0"
    assert record.output_contract_ref == "extension_run_result_identity_v1"
    assert record.workload_digest.startswith("sha256:")


def test_odr_workload_record_helper_keeps_run_arbiter_out_of_authority_input_shape() -> None:
    """Layer: unit. Verifies the ODR arbiter start path resolves its workload record through one catalog-local helper."""
    record = _resolve_odr_arbiter_control_plane_workload_from_contract(
        contract_payload={
            "workload_contract_version": WORKLOAD_CONTRACT_VERSION_V1,
            "workload_type": "odr",
            "units": [{"unit_id": "pair:1"}],
            "required_materials": [],
            "expected_artifacts": ["out/index.json"],
            "validators": ["shape", "trace"],
            "summary_targets": ["out/index.json"],
            "provenance_targets": [],
        },
        output_contract_ref="out/index.json",
        runner="run_odr_quant_sweep.py",
    )

    assert record.workload_id == "odr-run-arbiter"
    assert record.workload_version == WORKLOAD_CONTRACT_VERSION_V1
    assert record.output_contract_ref == "out/index.json"
    assert record.workload_digest.startswith("sha256:")


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
