from __future__ import annotations

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.llm.local_model_provider import ModelResponse
from orket.application.services.sdk_llm_provider import LocalModelCapabilityProvider
from orket_extension_sdk.llm import GenerateRequest

pytestmark = pytest.mark.contract

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

    async def close(self):
        return None


def test_local_model_capability_provider_maps_generate_response(monkeypatch) -> None:
    """Layer: contract. Verifies SDK model.generate adapter maps provider payload to SDK response contract."""
    monkeypatch.setattr("orket.application.services.sdk_llm_provider.create_local_model_provider",
                        lambda **kwargs: _FakeLocalModelProvider())
    provider = LocalModelCapabilityProvider(model="fake", temperature=0.1, seed=123)
    try:
        response = provider.generate(GenerateRequest(system_prompt="system", user_message="hello"))
    finally:
        provider.close()

    assert response.text == "hello from fake provider"
    assert response.model == "fake-model"
    assert response.latency_ms == 17
    assert response.input_tokens == 11
    assert response.output_tokens == 7


@pytest.mark.asyncio
async def test_local_model_capability_provider_generate_in_running_loop(monkeypatch) -> None:
    """Layer: contract. Native generation refuses the event loop and works through an owned worker."""
    monkeypatch.setattr("orket.application.services.sdk_llm_provider.create_local_model_provider",
                        lambda **kwargs: _FakeLocalModelProvider())
    provider = LocalModelCapabilityProvider(model="fake", temperature=0.1, seed=123)
    request = GenerateRequest(system_prompt="", user_message="hello")
    try:
        with pytest.raises(RuntimeError, match="E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER"):
            provider.generate(request)
        response = await run_owned_thread(lambda: provider.generate(request), label="SDK contract generation")
        assert response.text == "hello from fake provider"
    finally:
        await run_owned_thread(provider.close, label="SDK contract cleanup")
