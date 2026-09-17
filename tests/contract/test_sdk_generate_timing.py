"""The public generation response keeps unavailable latency distinct from zero."""
from __future__ import annotations

from dataclasses import asdict

import pytest

from orket.adapters.llm.local_model_provider import ModelResponse
from orket.capabilities.sdk_llm_provider import LocalModelCapabilityProvider
from orket.capabilities.sdk_static_provider import StaticLLMCapabilityProvider
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse, NullLLMProvider


@pytest.mark.parametrize("latency", [None, True, False, -1, "12", 2.5, float("nan"), 0, 17])
# Layer: contract
def test_sdk_generation_preserves_unavailable_latency(monkeypatch, latency):
    class ObservationProvider:
        model = "fixture"

        async def complete(self, *, messages, runtime_context):
            return ModelResponse(content="answer",raw={"latency_ms":latency,"input_tokens":4,"output_tokens":2})

    monkeypatch.setattr("orket.capabilities.sdk_llm_provider.LocalModelProvider",lambda **kwargs: ObservationProvider())
    provider = LocalModelCapabilityProvider(model="fixture",temperature=0,seed=0)
    result = provider.generate(GenerateRequest(system_prompt="",user_message="question"))
    measured = type(latency) is int and latency >= 0
    assert result.latency_ms == (latency if measured else None)
    assert result.latency_posture == ("reported" if measured else "unavailable")
    assert result.schema_version == "model_generate_response.v1"
    assert asdict(result)["latency_posture"] == result.latency_posture
    assert result.text == "answer" and (result.input_tokens,result.output_tokens) == (4,2)


@pytest.mark.parametrize("provider", [NullLLMProvider(), StaticLLMCapabilityProvider(text="fixture")])
# Layer: contract
def test_non_inference_sdk_providers_do_not_claim_zero_latency(provider):
    result = provider.generate(GenerateRequest(system_prompt="",user_message="question"))
    assert result.latency_ms is None and result.latency_posture == "unavailable"


@pytest.mark.parametrize("latency", [True, -1, "12", 2.5, float("nan"), float("inf")])
# Layer: contract
def test_public_generate_response_rejects_invalid_latency(latency):
    with pytest.raises(ValueError,match="E_SDK_GENERATE_LATENCY_INVALID"):
        GenerateResponse(text="answer",model="fixture",latency_ms=latency)
