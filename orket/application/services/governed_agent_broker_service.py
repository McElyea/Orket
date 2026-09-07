from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError  # type: ignore[attr-defined]

from orket.application.services.governed_agent_ports import (
    GovernedAgentBrokerCallRepository,
    GovernedAgentCapabilityBroker,
    GovernedAgentInvocationBinding,
    GovernedAgentIterationRepository,
)
from orket.exceptions import ModelConnectionError, ModelProviderError, ModelTimeoutError
from orket_extension_sdk import (
    AgentIdentity,
    AgentIterationRequest,
    AgentMemoryEntry,
    AgentMemoryQueryRequest,
    AgentMemoryQueryResult,
    AgentModelCallRequest,
    AgentModelCallResult,
    AgentModelUseReceipt,
    canonical_digest_sha256,
)

UsagePosture = Literal["measured", "estimated", "unknown"]
SubstitutionPosture = Literal["requested", "substituted", "degraded"]
ModelObservationStatus = Literal["returned", "failed", "cancelled", "timed_out"]


@dataclass(frozen=True, slots=True)
class GovernedAgentResolvedModelProfile:
    requested_profile_ref: str
    resolved_profile_ref: str
    provider: str
    provider_version: str | None
    model: str
    model_digest: str | None
    substitution_posture: SubstitutionPosture = "requested"
    supports_json: bool = True
    supports_tools: bool = False
    supports_streaming: bool = False


@dataclass(frozen=True, slots=True)
class GovernedAgentModelObservation:
    response: Any
    usage_posture: UsagePosture
    input_tokens: int | None
    output_tokens: int | None
    estimate_source: str | None
    latency_ms: int
    finish_reason: str | None
    truncated: bool = False
    status: ModelObservationStatus = "returned"
    normalized_reason: str | None = None


@dataclass(frozen=True, slots=True)
class GovernedAgentMemoryObservation:
    entries: tuple[AgentMemoryEntry, ...]


class GovernedAgentModelProvider(Protocol):
    async def call(
        self,
        *,
        request: AgentModelCallRequest,
        profile: GovernedAgentResolvedModelProfile,
    ) -> GovernedAgentModelObservation: ...


class GovernedAgentMemoryProvider(Protocol):
    async def query(
        self,
        *,
        request: AgentMemoryQueryRequest,
    ) -> GovernedAgentMemoryObservation: ...


class GovernedAgentHostBroker(GovernedAgentCapabilityBroker):
    """Host-owned broker with durable reservations and independently retained receipts."""

    def __init__(
        self,
        *,
        iteration_repository: GovernedAgentIterationRepository,
        call_repository: GovernedAgentBrokerCallRepository,
        model_provider: GovernedAgentModelProvider,
        model_profiles: Mapping[str, GovernedAgentResolvedModelProfile],
        memory_provider: GovernedAgentMemoryProvider | None = None,
    ) -> None:
        self._iterations = iteration_repository
        self._calls = call_repository
        self._model_provider = model_provider
        self._profiles = dict(model_profiles)
        self._memory_provider = memory_provider

    async def dispatch_call(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        operation: Literal["model.call.v1", "memory.query.v1"],
        call_payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        retained = await self._iterations.get_dispatch_binding(invocation_id=binding.invocation_id)
        request_payload = await self._iterations.get_dispatch_request(invocation_id=binding.invocation_id)
        if retained != binding or request_payload is None:
            raise ValueError("E_AGENT_BROKER_BINDING_STALE")
        iteration = AgentIterationRequest.from_wire(dict(request_payload))
        if operation == "model.call.v1":
            return await self._dispatch_model(binding, iteration, dict(call_payload))
        return await self._dispatch_memory(binding, iteration, dict(call_payload))

    async def _dispatch_model(
        self,
        binding: GovernedAgentInvocationBinding,
        iteration: AgentIterationRequest,
        call_payload: dict[str, Any],
    ) -> Mapping[str, Any]:
        call = AgentModelCallRequest.from_wire(call_payload)
        _require_identity(binding, call.identity)
        admitted = _admitted_model_profile(iteration, call)
        profile_ref = str(admitted.profile_ref or "")
        profile = self._profiles.get(profile_ref)
        if profile is None or profile.requested_profile_ref != profile_ref:
            raise ValueError("E_AGENT_MODEL_PROFILE_UNAVAILABLE")
        _require_provider_features(call, profile)
        _validate_response_schema(call)
        request_digest = _digest(call.to_wire())
        reservation = await self._calls.reserve_call(
            binding=binding,
            operation="model.call.v1",
            call_id=call.call_id,
            role=call.role,
            request_digest=request_digest,
            reserved_input_tokens=call.max_input_tokens,
            reserved_output_tokens=call.max_output_tokens,
        )
        if reservation.status == "idempotent" and reservation.retained_result_payload is not None:
            return dict(reservation.retained_result_payload)
        if reservation.status != "prepared":
            raise ValueError(f"E_AGENT_BROKER_RESERVATION_{reservation.status.upper()}")
        try:
            observation = await self._model_provider.call(request=call, profile=profile)
            result, charged_input, charged_output = _model_result(call, profile, observation)
            payload = result.to_wire()
            await self._calls.complete_call(
                binding=binding,
                call_id=call.call_id,
                request_digest=request_digest,
                result_payload=payload,
                result_digest=_digest(payload),
                charged_input_tokens=charged_input,
                charged_output_tokens=charged_output,
            )
            return cast(dict[str, Any], payload)
        except (ModelConnectionError, ModelTimeoutError, ModelProviderError) as exc:
            reason = _provider_failure_reason(exc)
            await self._calls.mark_call_uncertain(
                binding=binding,
                call_id=call.call_id,
                normalized_reason=reason,
            )
            raise ValueError(reason) from exc
        except (OSError, RuntimeError, TimeoutError, ValueError):
            await self._calls.mark_call_uncertain(
                binding=binding,
                call_id=call.call_id,
                normalized_reason="provider_result_uncertain",
            )
            raise

    async def _dispatch_memory(
        self,
        binding: GovernedAgentInvocationBinding,
        iteration: AgentIterationRequest,
        call_payload: dict[str, Any],
    ) -> Mapping[str, Any]:
        call = AgentMemoryQueryRequest.from_wire(call_payload)
        _require_identity(binding, call.identity)
        if "memory.query.v1" not in iteration.admitted_capabilities:
            raise ValueError("E_AGENT_MEMORY_CAPABILITY_UNADMITTED")
        request_digest = _digest(call.to_wire())
        reservation = await self._calls.reserve_call(
            binding=binding,
            operation="memory.query.v1",
            call_id=call.call_id,
            role=call.role,
            request_digest=request_digest,
            reserved_input_tokens=0,
            reserved_output_tokens=0,
        )
        if reservation.status == "idempotent" and reservation.retained_result_payload is not None:
            return dict(reservation.retained_result_payload)
        if reservation.status != "prepared":
            raise ValueError(f"E_AGENT_BROKER_RESERVATION_{reservation.status.upper()}")
        result = await self._memory_result(call)
        payload = result.to_wire()
        await self._calls.complete_call(
            binding=binding,
            call_id=call.call_id,
            request_digest=request_digest,
            result_payload=payload,
            result_digest=_digest(payload),
            charged_input_tokens=0,
            charged_output_tokens=0,
        )
        return cast(dict[str, Any], payload)

    async def _memory_result(self, call: AgentMemoryQueryRequest) -> AgentMemoryQueryResult:
        if self._memory_provider is None:
            return AgentMemoryQueryResult(
                identity=call.identity,
                call_id=call.call_id,
                status="blocked",
                entries=(),
                normalized_reason="memory_provider_unavailable",
            )
        observation = await self._memory_provider.query(request=call)
        if len(observation.entries) > call.max_items:
            raise ValueError("E_AGENT_MEMORY_ITEM_BUDGET_EXCEEDED")
        payload_bytes = sum(len(entry.content.canonical.encode("utf-8")) for entry in observation.entries)
        if payload_bytes > call.max_content_bytes:
            raise ValueError("E_AGENT_MEMORY_CONTENT_BUDGET_EXCEEDED")
        return AgentMemoryQueryResult(
            identity=call.identity,
            call_id=call.call_id,
            status="returned",
            entries=observation.entries,
            normalized_reason=None,
        )


def _admitted_model_profile(
    iteration: AgentIterationRequest,
    call: AgentModelCallRequest,
):
    profiles = {profile.role: profile for profile in iteration.model_profiles}
    profile = profiles.get(call.role)
    if profile is None:
        raise ValueError("E_AGENT_MODEL_ROLE_UNADMITTED")
    if call.profile_ref != profile.profile_ref or call.capability_class != profile.capability_class:
        raise ValueError("E_AGENT_MODEL_PROFILE_MISMATCH")
    if (
        call.max_input_tokens > profile.max_input_tokens
        or call.max_output_tokens > profile.max_output_tokens
        or call.timeout_ms > profile.timeout_ms
        or call.response_mode != profile.response_mode
        or call.streaming_preference == "required"
    ):
        raise ValueError("E_AGENT_MODEL_PROFILE_LIMIT_EXCEEDED")
    return profile


def _model_result(
    call: AgentModelCallRequest,
    profile: GovernedAgentResolvedModelProfile,
    observation: GovernedAgentModelObservation,
) -> tuple[AgentModelCallResult, int, int]:
    if observation.usage_posture == "unknown":
        if observation.input_tokens is not None or observation.output_tokens is not None:
            raise ValueError("E_AGENT_MODEL_UNKNOWN_USAGE_HAS_COUNTS")
        charged_input = call.max_input_tokens
        charged_output = call.max_output_tokens
    else:
        if observation.input_tokens is None or observation.output_tokens is None:
            raise ValueError("E_AGENT_MODEL_KNOWN_USAGE_MISSING_COUNTS")
        charged_input = observation.input_tokens
        charged_output = observation.output_tokens
    if charged_input > call.max_input_tokens or charged_output > call.max_output_tokens:
        raise ValueError("E_AGENT_MODEL_OBSERVED_USAGE_EXCEEDED")
    status = observation.status
    normalized_reason = observation.normalized_reason
    if status == "returned" and not _response_matches_contract(call, observation.response):
        status = "failed"
        normalized_reason = "model_response_contract_failed"
    if status == "returned":
        response = observation.response
        response_digest = _digest_value(response)
        normalized_reason = None
    else:
        if normalized_reason is None:
            raise ValueError("E_AGENT_MODEL_FAILED_REASON_REQUIRED")
        response = None
        response_digest = None
    receipt = AgentModelUseReceipt(
        identity=call.identity,
        call_id=call.call_id,
        role=call.role,
        requested_profile_ref=profile.requested_profile_ref,
        resolved_profile_ref=profile.resolved_profile_ref,
        provider=profile.provider,
        provider_version=profile.provider_version,
        model=profile.model,
        model_digest=profile.model_digest,
        status=status,
        usage_posture=observation.usage_posture,
        input_tokens=observation.input_tokens,
        output_tokens=observation.output_tokens,
        estimate_source=observation.estimate_source,
        charged_input_tokens=charged_input,
        charged_output_tokens=charged_output,
        latency_ms=observation.latency_ms,
        finish_reason=observation.finish_reason,
        truncated=observation.truncated,
        substitution_posture=profile.substitution_posture,
    )
    result = AgentModelCallResult(
        identity=call.identity,
        call_id=call.call_id,
        role=call.role,
        response=response,
        response_digest=response_digest,
        receipt=receipt,
        normalized_reason=normalized_reason,
    )
    result.to_wire()
    return result, charged_input, charged_output


def _require_provider_features(
    call: AgentModelCallRequest,
    profile: GovernedAgentResolvedModelProfile,
) -> None:
    if call.response_mode == "json" and not profile.supports_json:
        raise ValueError("E_AGENT_MODEL_JSON_UNSUPPORTED")
    if call.tool_descriptions and not profile.supports_tools:
        raise ValueError("E_AGENT_MODEL_TOOLS_UNSUPPORTED")
    if call.streaming_preference == "required" and not profile.supports_streaming:
        raise ValueError("E_AGENT_MODEL_STREAMING_UNSUPPORTED")


def _validate_response_schema(call: AgentModelCallRequest) -> None:
    if call.response_mode != "json" or call.response_schema is None:
        return
    schema = call.response_schema.thaw()
    if not isinstance(schema, dict):
        raise ValueError("E_AGENT_MODEL_RESPONSE_SCHEMA_INVALID")
    try:
        Draft202012Validator.check_schema(schema)  # type: ignore[attr-defined]
    except SchemaError as exc:
        raise ValueError("E_AGENT_MODEL_RESPONSE_SCHEMA_INVALID") from exc


def _response_matches_contract(call: AgentModelCallRequest, response: Any) -> bool:
    if call.response_mode != "json" or call.response_schema is None:
        return True
    schema = call.response_schema.thaw()
    try:
        Draft202012Validator(schema).validate(response)
    except ValidationError:
        return False
    return True


def _provider_failure_reason(exc: ModelProviderError) -> str:
    if isinstance(exc, ModelConnectionError):
        return "E_AGENT_MODEL_PROVIDER_UNAVAILABLE"
    if isinstance(exc, ModelTimeoutError):
        return "E_AGENT_MODEL_PROVIDER_TIMEOUT"
    return "E_AGENT_MODEL_PROVIDER_UNCERTAIN"


def _require_identity(binding: GovernedAgentInvocationBinding, identity: AgentIdentity) -> None:
    if (
        identity.run_id != binding.run_id
        or identity.attempt_id != binding.attempt_id
        or identity.step_id != binding.step_id
        or identity.iteration_ordinal != binding.iteration_ordinal
        or identity.invocation_id != binding.invocation_id
        or identity.fencing_generation != binding.fencing_generation
    ):
        raise ValueError("E_AGENT_BROKER_CALL_IDENTITY_MISMATCH")


def _digest(payload: Mapping[str, Any]) -> str:
    return "sha256:" + cast(str, canonical_digest_sha256(dict(payload)))


def _digest_value(payload: Any) -> str:
    return "sha256:" + cast(str, canonical_digest_sha256(payload))
