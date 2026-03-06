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
async def test_local_model_provider_emits_usage_and_timings_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ORKET_MODEL_PROVIDER", raising=False)
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
        assert request.headers["x-orket-request-id"].startswith("orket-")
        assert bool(request.headers["x-orket-session-id"])
        assert request.headers["x-client-session"] == request.headers["x-orket-session-id"]
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
    assert response.raw["orket_request_id"].startswith("orket-")
    assert bool(response.raw["orket_session_id"])
    assert bool(response.raw["prompt_fingerprint"])
    assert response.raw["http"]["status_code"] == 200
    assert "content-type" in response.raw["http"]["response_headers"]
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


@pytest.mark.asyncio
async def test_local_model_provider_uses_runtime_context_for_orket_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="dummy")

    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-orket-session-id"] == "seat-42"
        assert request.headers["x-client-session"] == "seat-42"
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-ctx",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete(
        [{"role": "user", "content": "hello"}],
        runtime_context={"seat_id": "seat-42"},
    )
    await provider.client.aclose()
    assert response.raw["orket_session_id"] == "seat-42"


@pytest.mark.asyncio
async def test_local_model_provider_captures_openai_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="dummy")

    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-tool",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "read_file", "arguments": "{\"path\":\"README.md\"}"},
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete([{"role": "user", "content": "tool"}])
    await provider.client.aclose()
    assert response.raw["tool_calls"][0]["id"] == "call_1"


@pytest.mark.asyncio
async def test_local_model_provider_applies_local_prompt_profile_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="qwen3.5-4b")

    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["max_tokens"] == 512
        assert payload["top_p"] == 1.0
        assert payload["temperature"] == 0.0
        assert payload["stop"] == ["<|json_end|>", "</s>"]
        assert payload["seed"] == 41
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
    response = await provider.complete(
        [{"role": "user", "content": "hello"}],
        runtime_context={"protocol_governed_enabled": True, "local_prompt_task_class": "strict_json"},
    )
    await provider.client.aclose()
    assert response.raw["profile_id"] == "openai_compat.qwen.openai_messages.v1"
    assert response.raw["task_class"] == "strict_json"
    assert response.raw["template_hash_alg"] == "sha256"
