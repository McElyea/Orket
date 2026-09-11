from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.application.services.governed_agent_context_plan import validate_continuation_inputs
from orket.application.services.governed_agent_effect_resume_service import GovernedAgentEffectResumeService
from orket.application.services.governed_agent_effect_service import GovernedAgentEffectService
from orket.application.services.governed_agent_execution_composition import (
    PROVIDER_CHOICES,
    build_governed_agent_loop_service,
    governed_agent_configuration_digest,
    model_map_for_roles,
    select_governed_agent_provider,
)
from orket.application.services.governed_agent_loop_service import GovernedAgentLoopExecution
from orket.application.services.governed_agent_supervisor import (
    GovernedAgentWakeClaimGuard,
    GovernedAgentWakeDispatchResult,
)
from orket.application.services.governed_agent_wake_records import GovernedAgentWakeRecord
from orket.core.contracts import WorkloadRecord
from orket.core.domain import RunState
from orket.extensions.manager import ExtensionManager
from orket.extensions.models import GovernedAgentWorkloadLaunch
from orket_extension_sdk import AgentIterationRequest, AgentIterationResult

ProviderMode = Literal["deterministic_fixture", "llama_cpp", "lmstudio", "ollama", "openai_compat"]


@dataclass(frozen=True, slots=True)
class GovernedAgentProviderConfiguration:
    mode: ProviderMode
    default_model: str
    role_models: Mapping[str, str]
    ollama_base_url: str
    inventory_timeout_seconds: float
    capacity_limit: int
    provider_base_url: str = ""

    def __post_init__(self) -> None:
        if self.mode != "deterministic_fixture" and self.mode not in PROVIDER_CHOICES:
            raise ValueError("E_AGENT_PROVIDER_MODE_INVALID")
        if self.inventory_timeout_seconds <= 0 or self.capacity_limit < 1:
            raise ValueError("E_AGENT_PROVIDER_CAPACITY_CONFIGURATION_INVALID")


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeDispatchEnvelope:
    request_payload: Mapping[str, Any]
    creation_timestamp_utc: str
    decision_timestamps_utc: tuple[str, ...]
    next_lease_expiries_utc: tuple[str, ...]
    continuation_inputs: Mapping[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> GovernedAgentWakeDispatchEnvelope:
        allowed = {
            "schema_version",
            "request",
            "creation_timestamp_utc",
            "decision_timestamps_utc",
            "next_lease_expiries_utc",
            "trigger",
            "continuation_inputs",
        }
        if set(payload) - allowed:
            raise ValueError("E_AGENT_WAKE_DISPATCH_FIELD_UNKNOWN")
        if payload.get("schema_version") != "governed_agent_wake_dispatch.v1":
            raise ValueError("E_AGENT_WAKE_DISPATCH_VERSION_UNSUPPORTED")
        request_payload = payload.get("request")
        if not isinstance(request_payload, Mapping):
            raise ValueError("E_AGENT_WAKE_DISPATCH_REQUEST_REQUIRED")
        trigger = payload.get("trigger")
        if trigger is not None and not isinstance(trigger, Mapping):
            raise ValueError("E_AGENT_WAKE_TRIGGER_INVALID")
        request = AgentIterationRequest.from_wire(dict(request_payload))
        decision_timestamps = _timestamp_sequence(payload.get("decision_timestamps_utc"))
        next_lease_expiries = _timestamp_sequence(payload.get("next_lease_expiries_utc"), allow_empty=True)
        if len(decision_timestamps) < request.remaining_run_budget.iterations:
            raise ValueError("E_AGENT_WAKE_DECISION_TIMESTAMPS_INCOMPLETE")
        if len(next_lease_expiries) < max(0, request.remaining_run_budget.iterations - 1):
            raise ValueError("E_AGENT_WAKE_LEASE_EXPIRIES_INCOMPLETE")
        return cls(
            request_payload=dict(request_payload),
            creation_timestamp_utc=_utc_timestamp(payload.get("creation_timestamp_utc")),
            decision_timestamps_utc=decision_timestamps,
            next_lease_expiries_utc=next_lease_expiries,
            continuation_inputs=validate_continuation_inputs(request, payload.get("continuation_inputs")),
        )


class GovernedAgentWakeLoopDispatcher:
    """Dispatch one claimed wake through the canonical bounded agent loop."""

    def __init__(
        self,
        *,
        execution_repository: AsyncControlPlaneExecutionRepository,
        iteration_repository: AsyncGovernedAgentRepository,
        record_repository: AsyncControlPlaneRecordRepository,
        extension_manager: ExtensionManager,
        provider: GovernedAgentProviderConfiguration,
        effect_service: GovernedAgentEffectService,
        effect_resume_service: GovernedAgentEffectResumeService,
    ) -> None:
        self._execution = execution_repository
        self._iterations = iteration_repository
        self._records = record_repository
        self._extensions = extension_manager
        self._provider = provider
        self._effects = effect_service
        self._effect_resumes = effect_resume_service

    async def dispatch(
        self,
        *,
        wake: GovernedAgentWakeRecord,
        guard: GovernedAgentWakeClaimGuard,
    ) -> GovernedAgentWakeDispatchResult:
        envelope = GovernedAgentWakeDispatchEnvelope.from_payload(wake.payload)
        request = AgentIterationRequest.from_wire(dict(envelope.request_payload))
        await guard.ensure_active()
        workload_id = await self._resolve_workload_id(wake, request)
        if not self._capacity_admits(request):
            return GovernedAgentWakeDispatchResult(
                status="released",
                reason="provider_capacity_unavailable",
                child_confirmed_stopped=True,
            )
        launch = await asyncio.to_thread(self._extensions.resolve_governed_agent_workload, workload_id)
        await guard.ensure_active()
        if launch.workload_id != workload_id:
            raise ValueError("E_AGENT_WAKE_WORKLOAD_AUTHORITY_DRIFT")
        await self._activate_resume_if_required(wake, request, guard)
        execution = await self._execute_loop(
            request=request,
            envelope=envelope,
            launch=launch,
            guard=guard,
        )
        await self._prepare_effects(
            execution=execution,
            envelope=envelope,
            guard=guard,
        )
        await guard.ensure_active()
        current_run = await self._execution.get_run_record(run_id=execution.run.run_id)
        if current_run is None:
            raise ValueError("E_AGENT_WAKE_RUN_AUTHORITY_MISSING")
        if current_run.lifecycle_state is RunState.RECOVERY_PENDING:
            return GovernedAgentWakeDispatchResult(
                status="uncertain",
                reason=execution.normalized_reason or "agent_run_recovery_pending",
                child_confirmed_stopped=True,
                effect_uncertainty=True,
            )
        result_ref = current_run.final_truth_record_id or f"agent-run:{current_run.run_id}"
        return GovernedAgentWakeDispatchResult(
            status="completed",
            result_ref=result_ref,
            reason=execution.normalized_reason,
            child_confirmed_stopped=True,
        )

    async def _execute_loop(
        self,
        *,
        request: AgentIterationRequest,
        envelope: GovernedAgentWakeDispatchEnvelope,
        launch: GovernedAgentWorkloadLaunch,
        guard: GovernedAgentWakeClaimGuard,
    ) -> GovernedAgentLoopExecution:
        models = self._model_map(request)
        selection = await select_governed_agent_provider(
            request=request,
            launch=launch,
            deterministic_fixture=self._provider.mode == "deterministic_fixture",
            model_by_role=models,
            provider_name=self._provider.mode,
            provider_base_url=self._provider.provider_base_url,
            ollama_base_url=self._provider.ollama_base_url,
            inventory_timeout_seconds=self._provider.inventory_timeout_seconds,
        )
        try:
            service = build_governed_agent_loop_service(
                execution=self._execution,
                iterations=self._iterations,
                records=self._records,
                launch=launch,
                selection=selection,
                authority_guard=guard,
            )
            execution = await service.run_bounded(
                initial_request_payload=envelope.request_payload,
                workload_record=WorkloadRecord.model_validate(launch.control_plane_workload_record),
                extension_digest=launch.extension_digest,
                configuration_digest=governed_agent_configuration_digest(
                    launch,
                    selection.configuration_payload(),
                ),
                admission_receipt_ref=f"agent-catalog-admission:{launch.extension_id}:{launch.workload_id}",
                creation_timestamp_utc=envelope.creation_timestamp_utc,
                decision_timestamps_utc=envelope.decision_timestamps_utc,
                next_lease_expiries_utc=envelope.next_lease_expiries_utc,
                continuation_inputs_payload=envelope.continuation_inputs,
            )
        finally:
            await selection.close()
        return execution

    async def _activate_resume_if_required(
        self,
        wake: GovernedAgentWakeRecord,
        request: AgentIterationRequest,
        guard: GovernedAgentWakeClaimGuard,
    ) -> None:
        if wake.target_kind != "existing_run":
            return
        run = await self._execution.get_run_record(run_id=request.identity.run_id)
        if run is None:
            raise ValueError("E_AGENT_WAKE_TARGET_RUN_NOT_FOUND")
        if run.lifecycle_state is RunState.OPERATOR_BLOCKED or request.accepted_checkpoint_ref is not None:
            await self._effect_resumes.activate_resume(
                request=request,
                authority_guard=guard,
            )

    async def _prepare_effects(
        self,
        *,
        execution: GovernedAgentLoopExecution,
        envelope: GovernedAgentWakeDispatchEnvelope,
        guard: GovernedAgentWakeClaimGuard,
    ) -> None:
        if execution.run.lifecycle_state is not RunState.OPERATOR_BLOCKED:
            return
        if not execution.decisions or execution.decisions[-1].rule != "effect_approval_required":
            return
        snapshots = await self._iterations.list_iteration_snapshots(run_id=execution.run.run_id)
        if not snapshots:
            raise ValueError("E_AGENT_EFFECT_PREPARATION_ITERATION_MISSING")
        snapshot = max(snapshots, key=lambda item: item.binding.iteration_ordinal)
        if snapshot.result_payload is None:
            raise ValueError("E_AGENT_EFFECT_PREPARATION_RESULT_MISSING")
        request = AgentIterationRequest.from_wire(dict(snapshot.request_payload))
        result = AgentIterationResult.from_wire(dict(snapshot.result_payload))
        timestamp = envelope.decision_timestamps_utc[len(execution.decisions) - 1]
        for proposal in result.effect_proposals:
            preparation = await self._effects.prepare(
                request=request,
                proposal=proposal,
                created_at=timestamp,
                authority_guard=guard,
            )
            if preparation.receipt.state == "uncertain":
                return

    async def _resolve_workload_id(
        self,
        wake: GovernedAgentWakeRecord,
        request: AgentIterationRequest,
    ) -> str:
        if wake.target_kind == "new_run":
            workload_id = _required_text(wake.workload_id)
        else:
            if wake.target_run_id != request.identity.run_id:
                raise ValueError("E_AGENT_WAKE_TARGET_RUN_MISMATCH")
            run = await self._execution.get_run_record(run_id=request.identity.run_id)
            if run is None:
                raise ValueError("E_AGENT_WAKE_TARGET_RUN_NOT_FOUND")
            workload_id = run.workload_id
        return workload_id

    def _capacity_admits(self, request: AgentIterationRequest) -> bool:
        demands: tuple[int, int] = (
            int(request.remaining_run_budget.total_inference_concurrency),
            int(request.remaining_iteration_budget.total_inference_concurrency),
        )
        return max(demands) <= self._provider.capacity_limit

    def _model_map(self, request: AgentIterationRequest) -> dict[str, str]:
        if self._provider.mode == "deterministic_fixture":
            return {}
        return dict(
            model_map_for_roles(
                request,
                default_model=self._provider.default_model,
                role_overrides=self._provider.role_models,
            )
        )


def _required_text(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("E_AGENT_WAKE_DISPATCH_TEXT_REQUIRED")
    return normalized


def _text_sequence(value: object, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("E_AGENT_WAKE_DISPATCH_SEQUENCE_REQUIRED")
    result = tuple(_required_text(item) for item in value)
    if not result and not allow_empty:
        raise ValueError("E_AGENT_WAKE_DISPATCH_SEQUENCE_EMPTY")
    return result


def _timestamp_sequence(value: object, *, allow_empty: bool = False) -> tuple[str, ...]:
    return tuple(_utc_timestamp(item) for item in _text_sequence(value, allow_empty=allow_empty))


def _utc_timestamp(value: object) -> str:
    raw = _required_text(value)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("E_AGENT_WAKE_DISPATCH_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("E_AGENT_WAKE_DISPATCH_TIMESTAMP_NOT_UTC")
    return parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
