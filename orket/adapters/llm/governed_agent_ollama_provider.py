from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.application.services.governed_agent_broker_service import (
    GovernedAgentModelObservation,
    GovernedAgentResolvedModelProfile,
    UsagePosture,
)
from orket.exceptions import ModelTimeoutError
from orket.runtime.provider_runtime_target import ProviderRuntimeTarget, resolve_provider_runtime_target
from orket_extension_sdk import AgentIterationRequest, AgentModelCallRequest


@dataclass(frozen=True, slots=True)
class GovernedAgentOllamaRuntime:
    provider: GovernedAgentOllamaModelProvider
    profiles: dict[str, GovernedAgentResolvedModelProfile]
    targets: dict[str, ProviderRuntimeTarget]


class GovernedAgentOllamaModelProvider:
    """Adapts host-owned Ollama clients to governed, host-receipted model calls."""

    def __init__(self, clients: Mapping[str, LocalModelProvider]) -> None:
        self._clients = dict(clients)

    async def call(
        self,
        *,
        request: AgentModelCallRequest,
        profile: GovernedAgentResolvedModelProfile,
    ) -> GovernedAgentModelObservation:
        if profile.provider != "ollama":
            raise ValueError("E_AGENT_OLLAMA_PROFILE_PROVIDER_INVALID")
        client = self._clients.get(profile.model)
        if client is None:
            raise ValueError("E_AGENT_OLLAMA_MODEL_CLIENT_MISSING")
        messages = [message.model_dump(mode="json", exclude_none=True) for message in request.messages]
        context = {
            "protocol_governed_enabled": True,
            "local_prompting_mode": "enforce",
            "local_prompt_task_class": "strict_json" if request.response_mode == "json" else "completion",
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
        return _observation(model_response)

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()


async def prepare_governed_agent_ollama_runtime(
    *,
    request: AgentIterationRequest,
    model_by_role: Mapping[str, str],
    base_url: str = "",
    inventory_timeout_seconds: float = 30,
) -> GovernedAgentOllamaRuntime:
    requests_by_role = {item.role: item for item in request.model_profiles}
    if set(model_by_role) != set(requests_by_role):
        raise ValueError("E_AGENT_OLLAMA_ROLE_MODEL_MAP_MISMATCH")
    targets: dict[str, ProviderRuntimeTarget] = {}
    for role, requested_model in model_by_role.items():
        target = await resolve_provider_runtime_target(
            provider="ollama",
            requested_model=requested_model,
            base_url=base_url or None,
            timeout_s=inventory_timeout_seconds,
            auto_select_model=False,
            auto_load_local_model=False,
            model_load_timeout_s=inventory_timeout_seconds,
            model_ttl_sec=0,
        )
        if target.status != "OK" or not target.model_id:
            raise ValueError(f"E_AGENT_OLLAMA_MODEL_UNAVAILABLE:{role}:{requested_model}")
        targets[role] = target
    maximum_timeout = max(item.timeout_ms for item in requests_by_role.values()) / 1000
    unique_targets = {target.model_id: target for target in targets.values()}
    clients = {
        model_id: LocalModelProvider(
            model_id,
            temperature=0,
            timeout=max(1, int(maximum_timeout)),
            provider="ollama",
            base_url=target.base_url,
            connect_timeout_seconds=min(30, max(1, maximum_timeout)),
        )
        for model_id, target in unique_targets.items()
    }
    profiles = {
        str(requests_by_role[role].profile_ref): GovernedAgentResolvedModelProfile(
            requested_profile_ref=str(requests_by_role[role].profile_ref),
            resolved_profile_ref=f"ollama:{target.model_id}",
            provider="ollama",
            provider_version=_ollama_version(),
            model=target.model_id,
            model_digest=None,
            substitution_posture="requested",
            supports_json=True,
            supports_tools=False,
            supports_streaming=False,
        )
        for role, target in targets.items()
    }
    return GovernedAgentOllamaRuntime(
        provider=GovernedAgentOllamaModelProvider(clients),
        profiles=profiles,
        targets=targets,
    )


def _observation(model_response: ModelResponse) -> GovernedAgentModelObservation:
    raw = model_response.raw
    input_tokens = _optional_int(raw.get("input_tokens"))
    output_tokens = _optional_int(raw.get("output_tokens"))
    usage_posture: UsagePosture = (
        "measured" if input_tokens is not None and output_tokens is not None else "unknown"
    )
    finish_reason = _ollama_field(raw.get("ollama"), "done_reason")
    latency_ms = _optional_int(raw.get("latency_ms")) or 0
    try:
        response = json.loads(model_response.content)
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


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, int) and value >= 0 else None


def _ollama_field(payload: Any, field: str) -> str | None:
    value = payload.get(field) if isinstance(payload, Mapping) else getattr(payload, field, None)
    token = str(value or "").strip()
    return token or None


def _ollama_version() -> str | None:
    try:
        return version("ollama")
    except PackageNotFoundError:
        return None
