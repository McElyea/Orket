"""Explicit submission inputs and application ownership of a bounded agent run."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.application.services.governed_agent_commands import build_governed_agent_inspector
from orket.application.services.governed_agent_execution_composition import (
    GovernedAgentProviderSelection,
    build_governed_agent_loop_service,
    governed_agent_configuration_digest,
    model_map_for_roles,
    select_governed_agent_provider,
)
from orket.core.contracts import WorkloadRecord
from orket.extensions.manager import ExtensionManager
from orket.extensions.models import GovernedAgentWorkloadLaunch
from orket_extension_sdk import AgentIterationRequest


@dataclass(frozen=True, slots=True)
class GovernedAgentProviderOptions:
    deterministic_fixture: bool = False
    provider_name: str | None = None
    model: str = ""
    ollama_model: str = ""
    provider_base_url: str = ""
    ollama_base_url: str = ""
    role_models: tuple[tuple[str, str], ...] = ()
    inventory_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_models", tuple((str(role), str(model)) for role, model in self.role_models))


@dataclass(frozen=True, slots=True)
class GovernedAgentSubmission:
    workload_id: str
    project_root: Path
    catalog_path: Path
    request_path: Path
    continuation_inputs_path: Path | None
    creation_timestamp_utc: str
    decision_timestamps_utc: tuple[str, ...]
    next_lease_expiries_utc: tuple[str, ...]
    provider: GovernedAgentProviderOptions

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_timestamps_utc", tuple(self.decision_timestamps_utc))
        object.__setattr__(self, "next_lease_expiries_utc", tuple(self.next_lease_expiries_utc))


async def submit_governed_agent(*, db_path: Path, submission: GovernedAgentSubmission) -> dict[str, Any]:
    launch, request_payload, continuation_inputs = await run_owned_thread(
        lambda: _prepare_submission(submission), label="governed-agent-submission-inputs",
    )
    request = AgentIterationRequest.from_wire(request_payload)
    selection = await _select_provider(submission.provider, request, launch)
    try:
        execution = AsyncControlPlaneExecutionRepository(db_path)
        iterations = AsyncGovernedAgentRepository(db_path)
        service = build_governed_agent_loop_service(
            execution=execution, iterations=iterations, records=AsyncControlPlaneRecordRepository(db_path),
            launch=launch, selection=selection,
        )
        result = await service.run_bounded(
            initial_request_payload=request_payload,
            workload_record=WorkloadRecord.model_validate(launch.control_plane_workload_record),
            extension_digest=launch.extension_digest,
            configuration_digest=governed_agent_configuration_digest(launch, selection.configuration_payload()),
            admission_receipt_ref=f"agent-catalog-admission:{launch.extension_id}:{launch.workload_id}",
            creation_timestamp_utc=submission.creation_timestamp_utc,
            decision_timestamps_utc=submission.decision_timestamps_utc,
            next_lease_expiries_utc=submission.next_lease_expiries_utc,
            continuation_inputs_payload=continuation_inputs,
        )
    finally:
        await run_owned_io(selection.close, label="governed-agent-submission-provider-close", preserve_failure=True)
    inspection = await build_governed_agent_inspector(db_path, iterations=iterations).inspect(run_id=request.identity.run_id)
    return _execution_payload(result, selection, inspection, db_path)


def _prepare_submission(submission: GovernedAgentSubmission):
    # Called only by the owned worker above; catalog validation and reads are synchronous.
    manager = ExtensionManager(catalog_path=submission.catalog_path, project_root=submission.project_root)
    launch = manager.resolve_governed_agent_workload(submission.workload_id)
    request = _read_json_object(submission.request_path)
    continuation = _read_json_object(submission.continuation_inputs_path) if submission.continuation_inputs_path else None
    return launch, request, continuation


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("E_AGENT_REQUEST_OBJECT_REQUIRED")
    return payload


async def _select_provider(
    options: GovernedAgentProviderOptions, request: AgentIterationRequest, launch: GovernedAgentWorkloadLaunch,
) -> GovernedAgentProviderSelection:
    provider_name = options.provider_name or ("ollama" if options.ollama_model else "llama_cpp")
    if (options.ollama_model or options.ollama_base_url) and provider_name != "ollama":
        raise ValueError("E_AGENT_PROVIDER_OPTIONS_CONFLICT")
    models = {} if options.deterministic_fixture else model_map_for_roles(
        request, default_model=options.model or options.ollama_model, role_overrides=dict(options.role_models),
    )
    return await select_governed_agent_provider(
        request=request, launch=launch, deterministic_fixture=options.deterministic_fixture, model_by_role=models,
        provider_name=provider_name, provider_base_url=options.provider_base_url,
        ollama_base_url=options.ollama_base_url, inventory_timeout_seconds=options.inventory_timeout_seconds,
    )


def _execution_payload(execution_result, selection, inspection, db_path: Path) -> dict[str, Any]:
    successful = execution_result.final_truth is not None and execution_result.final_truth.result_class.value == "success"
    return {
        "ok": successful, "object_type": "governed_agent_execution",
        "proof_posture": selection.proof_posture, "observed_path": selection.observed_path,
        "observed_result": "success" if successful else "failure",
        "model_targets": selection.targets, "db_path": str(db_path),
        "run": execution_result.run.model_dump(mode="json"),
        "decisions": [decision.to_payload() for decision in execution_result.decisions],
        "final_truth": None if execution_result.final_truth is None else execution_result.final_truth.model_dump(mode="json"),
        "normalized_reason": execution_result.normalized_reason,
        "iterations": [] if inspection is None else inspection["iterations"],
    }
