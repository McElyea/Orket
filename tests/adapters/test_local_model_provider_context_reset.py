from __future__ import annotations

import json

import httpx
import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider


@pytest.mark.asyncio
async def test_openai_compat_context_reset_status_tracks_epoch_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration. Verifies explicit-session backends surface fresh vs unknown context truth across resets."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="dummy")
    seen_session_ids: list[str] = []

    async def _handler(request: httpx.Request) -> httpx.Response:
        seen_session_ids.append(request.headers["x-orket-session-id"])
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

    first = await provider.complete([{"role": "user", "content": "hello"}], runtime_context={"run_id": "run-42"})
    await provider.clear_context()
    second = await provider.complete([{"role": "user", "content": "hello"}], runtime_context={"run_id": "run-42"})
    third = await provider.complete([{"role": "user", "content": "hello"}], runtime_context={"run_id": "run-42"})
    await provider.close()

    assert seen_session_ids == ["run-42", "run-42-ctx1", "run-42-ctx1"]
    assert first.raw["provider_session_epoch"] == 0
    assert second.raw["provider_session_epoch"] == 1
    assert third.raw["provider_session_epoch"] == 1
    assert first.raw["context_reset_status"] == "fresh_context"
    assert second.raw["context_reset_status"] == "fresh_context"
    assert third.raw["context_reset_status"] == "context_unknown"


@pytest.mark.asyncio
async def test_ollama_context_reset_status_is_stateless_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: contract. Verifies stateless backends are labeled explicitly instead of implying reset semantics."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ORKET_MODEL_PROVIDER", raising=False)
    provider = LocalModelProvider(model="qwen2.5-coder:7b")

    class _CaptureClient:
        async def chat(self, model, messages, options, format=None):  # type: ignore[no-untyped-def]
            _ = (model, messages, options, format)
            return {
                "message": {"content": json.dumps({"ok": True})},
                "prompt_eval_count": 4,
                "eval_count": 2,
                "prompt_eval_duration": 100_000_000,
                "eval_duration": 90_000_000,
                "total_duration": 210_000_000,
            }

    provider.client = _CaptureClient()
    response = await provider.complete([{"role": "user", "content": "Return strict JSON"}])

    assert response.raw["provider_session_epoch"] is None
    assert response.raw["context_reset_status"] == "stateless_backend"
