from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.application.services.control_plane_workload_catalog import (
    _resolve_extension_control_plane_workload,
)
from orket.application.services.governed_agent_broker_service import (
    GovernedAgentModelObservation,
    GovernedAgentResolvedModelProfile,
)
from orket.application.services.governed_agent_example_inputs import (
    ticket_continuation_inputs as ticket_continuation_inputs,
)
from orket.application.services.governed_agent_example_inputs import (
    ticket_report_request,
)
from orket.application.services.governed_agent_fixture import (
    DeterministicAgentModelProvider,
    SecondIterationDeterministicVerifier,
)
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord, WorkloadRecord
from orket.core.contracts.governed_agent_ports import GovernedAgentInvocationBinding
from orket.core.domain import AttemptState, RunState
from orket_extension_sdk import AgentModelCallRequest, canonical_digest_sha256

TEMPLATE_ROOT = Path("docs/templates/governed_agent_external").resolve()


class DeterministicModelProvider(DeterministicAgentModelProvider):
    def __init__(self) -> None:
        self.roles: list[str] = []

    async def call(
        self,
        *,
        request: AgentModelCallRequest,
        profile: GovernedAgentResolvedModelProfile,
    ) -> GovernedAgentModelObservation:
        self.roles.append(request.role)
        return await super().call(request=request, profile=profile)


class UnexpectedBroker:
    async def dispatch_call(self, **_: Any) -> dict[str, Any]:
        raise AssertionError("workload must not call the broker")


SecondIterationVerifier = SecondIterationDeterministicVerifier


def agent_request(case_id: str = "mixed") -> dict[str, Any]:
    return ticket_report_request(case_id, now=datetime.now(UTC))


def staged_agent_request(case_id: str = "mixed") -> dict[str, Any]:
    return ticket_report_request(case_id, now=datetime.now(UTC), staged=True)


def binding_for(request: dict[str, Any]) -> GovernedAgentInvocationBinding:
    identity = request["identity"]
    return GovernedAgentInvocationBinding(
        run_id=identity["run_id"],
        attempt_id=identity["attempt_id"],
        step_id=identity["step_id"],
        iteration_ordinal=identity["iteration_ordinal"],
        invocation_id=identity["invocation_id"],
        fencing_generation=identity["fencing_generation"],
        cancellation_epoch=request["cancellation"]["cancellation_epoch"],
        deadline_utc=request["deadline_utc"],
        extension_digest="sha256:" + "e" * 64,
        policy_digest=request["policy_digest"],
        request_digest="sha256:" + canonical_digest_sha256(request),
    )


async def prepare_authority(
    db_path: Path,
    request: dict[str, Any],
    binding: GovernedAgentInvocationBinding,
) -> AsyncGovernedAgentRepository:
    control_plane = AsyncControlPlaneExecutionRepository(db_path)
    workload = agent_workload_record()
    current_run = await control_plane.get_run_record(run_id=binding.run_id)
    current_attempt = await control_plane.get_attempt_record(attempt_id=binding.attempt_id)
    current_step = await control_plane.get_step_record(step_id=binding.step_id)
    await control_plane.save_run_record(
        record=RunRecord(
            state_revision=current_run.state_revision if current_run else None,
            run_id=binding.run_id,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            policy_snapshot_id=str(request["policy_ref"]),
            policy_digest=binding.policy_digest,
            configuration_snapshot_id=f"agent-config:{binding.run_id}",
            configuration_digest="sha256:" + "c" * 64,
            creation_timestamp="2026-09-07T00:00:00Z",
            admission_decision_receipt_ref="agent-admission:test",
            namespace_scope=str(request["namespace_scope"][0]),
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=binding.attempt_id,
        )
    )
    await control_plane.save_attempt_record(
        record=AttemptRecord(
            state_revision=current_attempt.state_revision if current_attempt else None,
            attempt_id=binding.attempt_id,
            run_id=binding.run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="agent-state:initial",
            start_timestamp="2026-09-07T00:00:00Z",
        )
    )
    await control_plane.save_step_record(
        record=StepRecord(
            state_revision=current_step.state_revision if current_step else None,
            step_id=binding.step_id,
            attempt_id=binding.attempt_id,
            step_kind="governed_agent_iteration",
            input_ref=binding.request_digest,
            observed_result_classification="dispatch_prepared",
            closure_classification="step_open",
        )
    )
    repository = AsyncGovernedAgentRepository(db_path)
    prepared = await repository.prepare_dispatch(binding=binding, request_payload=request)
    assert prepared.status == "prepared"
    return repository


def resolved_profiles() -> dict[str, GovernedAgentResolvedModelProfile]:
    return {
        f"local.{role}": GovernedAgentResolvedModelProfile(
            requested_profile_ref=f"local.{role}",
            resolved_profile_ref=f"deterministic.{role}",
            provider="deterministic_fixture",
            provider_version="v1",
            model=f"fixture-{role}",
            model_digest="sha256:" + str(index) * 64,
        )
        for index, role in enumerate(("planner", "actor", "critic"), start=1)
    }


def agent_workload_record() -> WorkloadRecord:
    return _resolve_extension_control_plane_workload(
        workload_id="governed-agent-loop",
        workload_version="0.1.0",
        extension_id="governed.agent.starter",
        extension_version="0.1.0",
        entrypoint="governed_agent:GovernedTicketAgent",
        required_capabilities=("agent.iteration.v1",),
        contract_style="sdk_v0",
        manifest_digest_sha256="fixture",
    )
