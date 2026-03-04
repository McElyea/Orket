from __future__ import annotations

import json

import httpx
import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.exceptions import ModelProviderError


class _FakeClient:
    async def chat(self, model, messages, options):  # type: ignore[no-untyped-def]
        return {
            "message": {"content": "ok"},
            "prompt_eval_count": 12,
            "eval_count": 8,
            "prompt_eval_duration": 120_000_000,
            "eval_duration": 320_000_000,
            "total_duration": 500_000_000,
        }


@pytest.mark.asyncio
async def test_local_model_provider_emits_usage_and_timings_payload() -> None:
    provider = LocalModelProvider(model="dummy")
    provider.client = _FakeClient()

    response = await provider.complete([{"role": "user", "content": "hello"}])

    assert isinstance(response, ModelResponse)
    assert response.content == "ok"
    assert response.raw["usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 8,
        "total_tokens": 20,
    }
    assert response.raw["timings"] == {
        "prompt_ms": 120.0,
        "predicted_ms": 320.0,
        "total_ms": 500.0,
    }


def test_local_model_provider_ns_to_ms_is_type_strict() -> None:
    assert LocalModelProvider._ns_to_ms(1_000_000) == 1.0
    assert LocalModelProvider._ns_to_ms(2.5) == 2.5 / 1_000_000.0
    assert LocalModelProvider._ns_to_ms("bad") is None


@pytest.mark.asyncio
async def test_local_model_provider_lmstudio_openai_compat_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="dummy")

    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "dummy"
        assert isinstance(payload["messages"], list)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete([{"role": "user", "content": "hello"}])
    await provider.client.aclose()

    assert isinstance(response, ModelResponse)
    assert response.content == "ok"
    assert response.raw["provider"] == "openai-compat"
    assert response.raw["provider_backend"] == "lmstudio"
    assert response.raw["usage"] == {
        "prompt_tokens": 7,
        "completion_tokens": 3,
        "total_tokens": 10,
    }
    assert isinstance(response.raw["timings"]["prompt_ms"], float)
    assert isinstance(response.raw["timings"]["predicted_ms"], float)


@pytest.mark.asyncio
async def test_local_model_provider_honors_bench_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("ORKET_BENCH_TEMPERATURE", "0")
    monkeypatch.setenv("ORKET_BENCH_SEED", "1337")
    monkeypatch.setenv("ORKET_LLM_OPENAI_RESPONSE_FORMAT", "text")
    provider = LocalModelProvider(model="dummy", temperature=0.7, seed=None)

    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["temperature"] == 0.0
        assert payload["seed"] == 1337
        assert payload["response_format"] == {"type": "text"}
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete([{"role": "user", "content": "hello"}])
    await provider.client.aclose()
    assert isinstance(response, ModelResponse)


@pytest.mark.asyncio
async def test_local_model_provider_rejects_non_openai_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="dummy")
    called = False

    async def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    with pytest.raises(ModelProviderError, match="OpenAI-compatible messages require roles"):
        await provider.complete(
            [
                {"role": "coder", "content": "prior output"},
                {"role": "developer", "content": "system hint"},
            ]
        )
    await provider.client.aclose()
    assert called is False
