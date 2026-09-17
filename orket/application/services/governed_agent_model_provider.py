from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.application.services.governed_agent_broker_service import (
    GovernedAgentModelObservation,
    GovernedAgentResolvedModelProfile,
    UsagePosture,
)
from orket.core.contracts.provider_runtime import PROVIDER_CHOICES, ProviderRuntimeTarget
from orket.exceptions import ModelTimeoutError
from orket.runtime.config.provider_runtime_target import resolve_provider_runtime_target
from orket_extension_sdk import AgentIterationRequest, AgentModelCallRequest
from orket_extension_sdk.llm import nonnegative_int_or_none


@dataclass(frozen=True, slots=True)
class GovernedAgentLocalRuntime:
    provider: GovernedAgentLocalModelProvider
    profiles: dict[str, GovernedAgentResolvedModelProfile]
    targets: dict[str, ProviderRuntimeTarget]


class GovernedAgentLocalModelProvider:
    """Coordinates host-owned local provider clients to governed, host-receipted model calls."""

    def __init__(self, clients: Mapping[str, LocalModelProvider]) -> None:
        self._clients = dict(clients)

    async def call(
        self,
        *,
        request: AgentModelCallRequest,
        profile: GovernedAgentResolvedModelProfile,
    ) -> GovernedAgentModelObservation:
        if profile.provider not in PROVIDER_CHOICES:
            raise ValueError("E_AGENT_LOCAL_PROFILE_PROVIDER_INVALID")
        client = self._clients.get(profile.model)
        if client is None:
            raise ValueError("E_AGENT_LOCAL_MODEL_CLIENT_MISSING")
        if client.provider_name != profile.provider:
            raise ValueError("E_AGENT_LOCAL_PROFILE_PROVIDER_MISMATCH")
        messages = [message.model_dump(mode="json", exclude_none=True) for message in request.messages]
        context = {
            "protocol_governed_enabled": True,
            "local_prompting_mode": "enforce",
            "local_prompt_task_class": "strict_json" if request.response_mode == "json" else "concise_text",
            "local_prompt_max_output_tokens": request.max_output_tokens,
            "local_prompt_temperature": request.temperature,
            "local_prompt_stop_sequences": list(request.stop_sequences),
        }
        try:
            model_response = await asyncio.wait_for(
                client.complete(messages, runtime_context=context),
                timeout=request.timeout_ms / 1000,
            )
        except TimeoutError as exc:
            raise ModelTimeoutError(f"Governed model call timed out for role {request.role}.") from exc
        return _observation(model_response, response_mode=request.response_mode)

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()


async def prepare_governed_agent_local_runtime(
    *,
    request: AgentIterationRequest,
    model_by_role: Mapping[str, str],
    provider: str,
    base_url: str = "",
    inventory_timeout_seconds: float = 30,
) -> GovernedAgentLocalRuntime:
    if provider not in PROVIDER_CHOICES:
        raise ValueError("E_AGENT_PROVIDER_MODE_INVALID")
    requests_by_role = {item.role: item for item in request.model_profiles}
    if set(model_by_role) != set(requests_by_role):
        raise ValueError("E_AGENT_LOCAL_ROLE_MODEL_MAP_MISMATCH")
    targets: dict[str, ProviderRuntimeTarget] = {}
    for role, requested_model in model_by_role.items():
        target = await _resolve_exact_target(
            provider=provider, model=requested_model, role=role,
            base_url=base_url, timeout_seconds=inventory_timeout_seconds,
        )
        targets[role] = target
    maximum_timeout = max(item.timeout_ms for item in requests_by_role.values()) / 1000
    unique_targets = {target.model_id: target for target in targets.values()}
    clients = {
        model_id: LocalModelProvider(
            model_id,
            temperature=0,
            timeout=max(1, int(maximum_timeout)),
            provider=provider,
            base_url=target.base_url,
            runtime_target=target,
            connect_timeout_seconds=min(30, max(1, maximum_timeout)),
        )
        for model_id, target in unique_targets.items()
    }
    profiles = {
        str(requests_by_role[role].profile_ref): GovernedAgentResolvedModelProfile(
            requested_profile_ref=str(requests_by_role[role].profile_ref),
            resolved_profile_ref=f"{provider}:{target.model_id}",
            provider=provider,
            provider_version=None,
            model=target.model_id,
            model_digest=None,
            substitution_posture="requested",
            supports_json=True,
            supports_tools=False,
            supports_streaming=False,
        )
        for role, target in targets.items()
    }
    return GovernedAgentLocalRuntime(
        provider=GovernedAgentLocalModelProvider(clients),
        profiles=profiles,
        targets=targets,
    )


async def _resolve_exact_target(*, provider: str, model: str, role: str,
                                base_url: str, timeout_seconds: float) -> ProviderRuntimeTarget:
    if not model:
        raise ValueError(f"E_AGENT_LOCAL_MODEL_REQUIRED:{role}")
    try:
        target = await resolve_provider_runtime_target(
            provider=provider, requested_model=model, base_url=base_url or None,
            timeout_s=timeout_seconds, auto_select_model=False, auto_load_local_model=False,
            model_load_timeout_s=timeout_seconds, model_ttl_sec=0,
        )
    except httpx.HTTPError as exc:
        raise ValueError(f"E_AGENT_LOCAL_INVENTORY_UNAVAILABLE:{provider}:{type(exc).__name__}") from exc
    if target.status != "OK" or target.model_id != model:
        raise ValueError(f"E_AGENT_LOCAL_MODEL_UNAVAILABLE:{role}:{model}:{target.resolution_mode}")
    return target


def _observation(model_response: ModelResponse, *, response_mode: str) -> GovernedAgentModelObservation:
    raw = model_response.raw
    input_tokens = nonnegative_int_or_none(raw.get("input_tokens"))
    output_tokens = nonnegative_int_or_none(raw.get("output_tokens"))
    usage_posture: UsagePosture = (
        "measured" if input_tokens is not None and output_tokens is not None else "unknown"
    )
    if usage_posture == "unknown":
        input_tokens = output_tokens = None
    finish_reason = _finish_reason(raw)
    latency_ms = nonnegative_int_or_none(raw.get("latency_ms"))
    try:
        response = json.loads(model_response.content) if response_mode == "json" else model_response.content
    except json.JSONDecodeError:
        return GovernedAgentModelObservation(
            response=None,
            usage_posture=usage_posture,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimate_source=None,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            truncated=finish_reason in {"length", "max_tokens"},
            status="failed",
            normalized_reason="model_response_invalid_json",
        )
    return GovernedAgentModelObservation(
        response=response,
        usage_posture=usage_posture,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimate_source=None,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        truncated=finish_reason in {"length", "max_tokens"},
    )


def _response_field(payload: Any, field: str) -> str | None:
    value = payload.get(field) if isinstance(payload, Mapping) else getattr(payload, field, None)
    token = str(value or "").strip()
    return token or None


def _finish_reason(raw: Mapping[str, Any]) -> str | None:
    payload = raw.get("openai_compat")
    if isinstance(payload, Mapping):
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            return _response_field(choices[0], "finish_reason")
    return _response_field(raw.get("ollama"), "done_reason")
