# Layer: unit and contract

from __future__ import annotations

from typing import Any, cast

import pytest

from orket.adapters.llm.governed_agent_ollama_provider import GovernedAgentOllamaModelProvider
from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.application.services.governed_agent_broker_service import (
    GovernedAgentModelObservation,
    GovernedAgentResolvedModelProfile,
    _model_result,
)
from orket_extension_sdk import AgentModelCallRequest
from orket_extension_sdk.agent_fixtures import agent_model_call_request


class _FakeLocalModelProvider:
    def __init__(self, response: ModelResponse) -> None:
        self.response = response
        self.context: dict[str, Any] | None = None

    async def complete(self, messages, runtime_context=None) -> ModelResponse:
        self.context = dict(runtime_context or {})
        return self.response

    async def close(self) -> None:
        return None


def _profile() -> GovernedAgentResolvedModelProfile:
    return GovernedAgentResolvedModelProfile(
        requested_profile_ref="local.planner",
        resolved_profile_ref="ollama:qwen2.5:7b",
        provider="ollama",
        provider_version="test",
        model="qwen2.5:7b",
        model_digest=None,
    )


@pytest.mark.asyncio
async def test_adapter_records_measured_json_observation_and_host_limits() -> None:
    """Layer: unit. The Ollama adapter preserves usage and applies issued generation limits."""

    fake = _FakeLocalModelProvider(
        ModelResponse(
            content='{"counts":{"open":2}}',
            raw={
                "input_tokens": 21,
                "output_tokens": 8,
                "latency_ms": 17,
                "ollama": {"done_reason": "stop"},
            },
        )
    )
    provider = GovernedAgentOllamaModelProvider(
        {"qwen2.5:7b": cast(LocalModelProvider, fake)}
    )
    request = AgentModelCallRequest.from_wire(agent_model_call_request())

    observation = await provider.call(request=request, profile=_profile())

    assert observation.response == {"counts": {"open": 2}}
    assert observation.usage_posture == "measured"
    assert observation.input_tokens == 21
    assert observation.output_tokens == 8
    assert observation.finish_reason == "stop"
    assert fake.context is not None
    assert fake.context["local_prompt_max_output_tokens"] == request.max_output_tokens
    assert fake.context["local_prompt_temperature"] == request.temperature


@pytest.mark.asyncio
async def test_adapter_returns_host_receiptable_failure_for_invalid_json() -> None:
    """Layer: contract. Malformed JSON is a failed call, not fabricated output."""

    fake = _FakeLocalModelProvider(
        ModelResponse(
            content="not-json",
            raw={"input_tokens": 5, "output_tokens": 2, "latency_ms": 3, "ollama": {"done_reason": "stop"}},
        )
    )
    provider = GovernedAgentOllamaModelProvider(
        {"qwen2.5:7b": cast(LocalModelProvider, fake)}
    )

    observation = await provider.call(
        request=AgentModelCallRequest.from_wire(agent_model_call_request()),
        profile=_profile(),
    )

    assert observation.status == "failed"
    assert observation.response is None
    assert observation.normalized_reason == "model_response_invalid_json"


def test_host_turns_response_schema_mismatch_into_failed_receipt() -> None:
    """Layer: contract. Schema-invalid JSON can be repaired without losing charged usage."""

    request = AgentModelCallRequest.from_wire(agent_model_call_request())
    observation = GovernedAgentModelObservation(
        response={"unexpected": True},
        usage_posture="measured",
        input_tokens=12,
        output_tokens=4,
        estimate_source=None,
        latency_ms=9,
        finish_reason="stop",
    )

    result, charged_input, charged_output = _model_result(request, _profile(), observation)

    assert result.receipt.status == "failed"
    assert result.response.thaw() is None
    assert result.normalized_reason == "model_response_contract_failed"
    assert (charged_input, charged_output) == (12, 4)
