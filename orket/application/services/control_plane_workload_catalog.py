from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from orket.core.contracts import (
    WORKLOAD_CONTRACT_VERSION_V1,
    WorkloadRecord,
)
from orket.core.contracts.workload_identity import (
    _build_control_plane_workload_record,
    _build_control_plane_workload_record_from_workload_contract,
)
from orket.core.domain import CapabilityClass
from orket.schema import EpicConfig


CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF = "control_plane.contract.v1:RunRecord"
# Keep this local so application-service startup does not import the
# extension package just to build control-plane workload projections.
EXTENSION_WORKLOAD_OUTPUT_CONTRACT_REF = "extension_run_result_identity_v1"
CARDS_CONTROL_PLANE_WORKLOAD_ID = "cards-epic-execution"
SANDBOX_RUNTIME_WORKLOAD_VERSION = "docker_sandbox_runtime.v1"
_SUPPORTED_SANDBOX_TECH_STACKS = (
    "fastapi-react-postgres",
    "fastapi-vue-mongo",
    "csharp-razor-ef",
    "node-react-postgres",
    "django-react-postgres",
)

KERNEL_ACTION_WORKLOAD = _build_control_plane_workload_record(
    workload_id="kernel-action-path",
    workload_version="kernel_api.v1",
    input_contract_ref="kernel_api/v1",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
)

ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD = _build_control_plane_workload_record(
    workload_id="orchestrator-issue-dispatch",
    workload_version="orchestrator.issue_dispatch.v1",
    input_contract_ref="orchestrator.issue_dispatch.transition",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    declared_capabilities=[CapabilityClass.BOUNDED_LOCAL_MUTATION],
)

ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD = _build_control_plane_workload_record(
    workload_id="orchestrator-issue-scheduler",
    workload_version="orchestrator.issue_scheduler.v1",
    input_contract_ref="orchestrator.issue_scheduler.transition",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    declared_capabilities=[CapabilityClass.BOUNDED_LOCAL_MUTATION],
)

ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD = _build_control_plane_workload_record(
    workload_id="orchestrator-child-workload-composition",
    workload_version="orchestrator.child_workload_composition.v1",
    input_contract_ref="orchestrator.child_workload_composition.issue_creation",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    declared_capabilities=[CapabilityClass.BOUNDED_LOCAL_MUTATION],
)

TURN_TOOL_WORKLOAD = _build_control_plane_workload_record(
    workload_id="governed-turn-tools",
    workload_version="turn_executor.governed.v1",
    input_contract_ref="turn_executor.governed.input.v1",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
)

GITEA_STATE_WORKER_EXECUTION_WORKLOAD = _build_control_plane_workload_record(
    workload_id="gitea-state-worker-card-execution",
    workload_version="gitea_state_worker.v1",
    input_contract_ref="gitea.state_backend.claimed_card.v1",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    declared_capabilities=[CapabilityClass.EXTERNAL_MUTATION],
)

REVIEW_RUN_WORKLOAD = _build_control_plane_workload_record(
    workload_id="review-run-manual",
    workload_version="review_run.v0",
    input_contract_ref="docs/specs/REVIEW_RUN_V0.md",
    output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    declared_capabilities=[CapabilityClass.DETERMINISTIC_COMPUTE],
)

_SANDBOX_RUNTIME_WORKLOADS = {
    tech_stack: _build_control_plane_workload_record(
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

WorkloadAuthorityKind = Literal[
    "catalog_workload",
    "workload_contract_v1",
    "extension_manifest_workload",
]


@dataclass(frozen=True)
class WorkloadAuthorityInput:
    kind: WorkloadAuthorityKind
    workload_key: str | None = None
    workload_id: str | None = None
    workload_version: str | None = None
    contract_payload: Mapping[str, Any] | None = None
    output_contract_ref: str | None = None
    extension_id: str | None = None
    extension_version: str | None = None
    manifest_digest_sha256: str | None = None
    entrypoint: str | None = None
    required_capabilities: Sequence[str] = ()
    contract_style: str | None = None
    definition_payload: Mapping[str, Any] | None = None


_FIXED_CATALOG_WORKLOADS = {
    "kernel_action": KERNEL_ACTION_WORKLOAD,
    KERNEL_ACTION_WORKLOAD.workload_id: KERNEL_ACTION_WORKLOAD,
    "orchestrator_issue_dispatch": ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD,
    ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD.workload_id: ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD,
    "orchestrator_scheduler_transition": ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD,
    ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD.workload_id: ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD,
    "orchestrator_child_workload_composition": ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD,
    ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD.workload_id: ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD,
    "turn_tool": TURN_TOOL_WORKLOAD,
    TURN_TOOL_WORKLOAD.workload_id: TURN_TOOL_WORKLOAD,
    "gitea_state_worker_execution": GITEA_STATE_WORKER_EXECUTION_WORKLOAD,
    GITEA_STATE_WORKER_EXECUTION_WORKLOAD.workload_id: GITEA_STATE_WORKER_EXECUTION_WORKLOAD,
    "review_run": REVIEW_RUN_WORKLOAD,
    REVIEW_RUN_WORKLOAD.workload_id: REVIEW_RUN_WORKLOAD,
}


def resolve_control_plane_workload(authority_input: WorkloadAuthorityInput) -> WorkloadRecord:
    """External workload-authority seam for governed start paths."""
    if authority_input.kind == "catalog_workload":
        return _resolve_catalog_workload(authority_input.workload_key)
    if authority_input.kind == "workload_contract_v1":
        workload_id = _require_token(authority_input.workload_id, field_name="workload_id")
        output_contract_ref = _require_token(
            authority_input.output_contract_ref,
            field_name="output_contract_ref",
        )
        return _build_control_plane_workload_record_from_workload_contract(
            workload_id=workload_id,
            contract_payload=dict(authority_input.contract_payload or {}),
            output_contract_ref=output_contract_ref,
            definition_payload=dict(authority_input.definition_payload or {}),
        )
    if authority_input.kind == "extension_manifest_workload":
        workload_id = _require_token(authority_input.workload_id, field_name="workload_id")
        workload_version = _require_token(authority_input.workload_version, field_name="workload_version")
        extension_id = _require_token(authority_input.extension_id, field_name="extension_id")
        extension_version = _require_token(authority_input.extension_version, field_name="extension_version")
        contract_style = _require_token(authority_input.contract_style, field_name="contract_style")
        return _build_control_plane_workload_record(
            workload_id=workload_id,
            workload_version=workload_version,
            input_contract_ref=f"extension_manifest:{contract_style}",
            output_contract_ref=EXTENSION_WORKLOAD_OUTPUT_CONTRACT_REF,
            definition_payload={
                "extension_id": extension_id,
                "extension_version": extension_version,
                "entrypoint": str(authority_input.entrypoint or "").strip(),
                "required_capabilities": [
                    str(capability).strip()
                    for capability in authority_input.required_capabilities
                    if str(capability).strip()
                ],
                "contract_style": contract_style,
                "manifest_digest_sha256": str(authority_input.manifest_digest_sha256 or "").strip(),
            },
        )
    raise ValueError(f"unsupported workload authority kind={authority_input.kind!r}")


def control_plane_workload_for_key(workload_key: str) -> WorkloadRecord:
    return resolve_control_plane_workload(
        WorkloadAuthorityInput(
            kind="catalog_workload",
            workload_key=workload_key,
        )
    )


def _resolve_cards_control_plane_workload_from_contract(
    *,
    contract_payload: Mapping[str, Any],
    department: str,
) -> WorkloadRecord:
    return resolve_control_plane_workload(
        WorkloadAuthorityInput(
            kind="workload_contract_v1",
            workload_id=CARDS_CONTROL_PLANE_WORKLOAD_ID,
            contract_payload=dict(contract_payload),
            output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
            definition_payload={"department": str(department)},
        )
    )


def _resolve_odr_arbiter_control_plane_workload_from_contract(
    *,
    contract_payload: Mapping[str, Any],
    output_contract_ref: str,
    runner: str,
) -> WorkloadRecord:
    return resolve_control_plane_workload(
        WorkloadAuthorityInput(
            kind="workload_contract_v1",
            workload_id="odr-run-arbiter",
            contract_payload=dict(contract_payload),
            output_contract_ref=output_contract_ref,
            definition_payload={"runner": str(runner)},
        )
    )


def _resolve_extension_control_plane_workload(
    *,
    workload_id: str,
    workload_version: str,
    extension_id: str,
    extension_version: str,
    entrypoint: str,
    required_capabilities: Sequence[str],
    contract_style: str,
    manifest_digest_sha256: str,
) -> WorkloadRecord:
    return resolve_control_plane_workload(
        WorkloadAuthorityInput(
            kind="extension_manifest_workload",
            workload_id=workload_id,
            workload_version=workload_version,
            extension_id=extension_id,
            extension_version=extension_version,
            entrypoint=entrypoint,
            required_capabilities=tuple(required_capabilities),
            contract_style=contract_style,
            manifest_digest_sha256=manifest_digest_sha256,
        )
    )


def _resolve_catalog_workload(workload_key: str | None) -> WorkloadRecord:
    normalized = _require_token(workload_key, field_name="workload_key")
    fixed = _FIXED_CATALOG_WORKLOADS.get(normalized)
    if fixed is not None:
        return fixed
    if normalized in _SANDBOX_RUNTIME_WORKLOADS:
        return _SANDBOX_RUNTIME_WORKLOADS[normalized]
    sandbox_prefix = "sandbox-workload:"
    if normalized.startswith(sandbox_prefix):
        return sandbox_runtime_workload_for_tech_stack(normalized.removeprefix(sandbox_prefix))
    raise ValueError(f"unsupported catalog workload_key={normalized!r}")


def _require_token(value: str | None, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def build_cards_workload_contract(
    *,
    epic: EpicConfig,
    run_id: str,
    build_id: str,
    workspace: Path,
    department: str,
) -> dict[str, Any]:
    units: list[dict[str, Any]] = []
    for issue in epic.issues:
        units.append(
            {
                "unit_id": f"card:{issue.id}",
                "card_id": issue.id,
                "seat": issue.seat,
                "priority": issue.priority,
                "depends_on": list(issue.depends_on or []),
            }
        )

    observability_root = workspace / "observability" / run_id
    required_materials = [
        {"kind": "asset", "value": f"epics/{epic.name}.json"},
        {"kind": "asset", "value": f"teams/{epic.team}.json"},
        {"kind": "asset", "value": f"environments/{epic.environment}.json"},
    ]
    expected_artifacts = [
        str((workspace / "agent_output" / "observability" / "runtime_events.jsonl").as_posix()),
        str(observability_root.as_posix()),
    ]
    summary_targets = [str((workspace / "agent_output" / "observability" / "runtime_events.jsonl").as_posix())]
    provenance_targets = [str((workspace / "observability" / run_id).as_posix())]

    return {
        "workload_contract_version": WORKLOAD_CONTRACT_VERSION_V1,
        "workload_type": "cards",
        "units": units,
        "required_materials": required_materials,
        "expected_artifacts": sorted(expected_artifacts),
        "validators": ["shape", "trace"],
        "summary_targets": summary_targets,
        "provenance_targets": provenance_targets,
    }


def sandbox_runtime_workload_for_tech_stack(tech_stack: object) -> WorkloadRecord:
    normalized = str(getattr(tech_stack, "value", tech_stack) or "").strip().lower()
    try:
        return control_plane_workload_for_key(normalized)
    except ValueError as exc:
        supported = ", ".join(_SUPPORTED_SANDBOX_TECH_STACKS)
        raise ValueError(f"unsupported sandbox tech_stack={normalized!r}; expected one of {supported}") from exc


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
    "CARDS_CONTROL_PLANE_WORKLOAD_ID",
    "CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF",
    "EXTENSION_WORKLOAD_OUTPUT_CONTRACT_REF",
    "GITEA_STATE_WORKER_EXECUTION_WORKLOAD",
    "KERNEL_ACTION_WORKLOAD",
    "ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD",
    "ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD",
    "ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD",
    "REVIEW_RUN_WORKLOAD",
    "SANDBOX_RUNTIME_WORKLOAD_VERSION",
    "TURN_TOOL_WORKLOAD",
    "WorkloadAuthorityInput",
    "build_cards_workload_contract",
    "control_plane_workload_for_key",
    "governed_control_plane_workloads",
    "resolve_control_plane_workload",
    "sandbox_runtime_workload_for_tech_stack",
]
