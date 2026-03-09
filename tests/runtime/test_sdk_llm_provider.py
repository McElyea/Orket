from __future__ import annotations

import pytest

from orket.adapters.llm.local_model_provider import ModelResponse
from orket.capabilities.sdk_llm_provider import LocalModelCapabilityProvider
from orket_extension_sdk.llm import GenerateRequest


class _FakeLocalModelProvider:
    model = "fake-model"

    async def complete(self, *, messages, runtime_context):  # noqa: ANN001
        assert messages[-1]["role"] == "user"
        assert isinstance(runtime_context, dict)
        return ModelResponse(
            content="hello from fake provider",
            raw={
                "model": "fake-model",
                "latency_ms": 17,
                "input_tokens": 11,
                "output_tokens": 7,
            },
        )


def test_local_model_capability_provider_maps_generate_response() -> None:
    """Layer: contract. Verifies SDK model.generate adapter maps provider payload to SDK response contract."""
    provider = LocalModelCapabilityProvider(model="fake", temperature=0.1, seed=123)
    provider._provider = _FakeLocalModelProvider()  # type: ignore[assignment]

    response = provider.generate(GenerateRequest(system_prompt="system", user_message="hello"))

    assert response.text == "hello from fake provider"
    assert response.model == "fake-model"
    assert response.latency_ms == 17
    assert response.input_tokens == 11
    assert response.output_tokens == 7


@pytest.mark.asyncio
async def test_local_model_capability_provider_generate_in_running_loop() -> None:
    """Layer: integration. Verifies sync generate bridge remains callable while an event loop is active."""
    provider = LocalModelCapabilityProvider(model="fake", temperature=0.1, seed=123)
    provider._provider = _FakeLocalModelProvider()  # type: ignore[assignment]

    response = provider.generate(GenerateRequest(system_prompt="", user_message="hello"))
    assert response.text == "hello from fake provider"
