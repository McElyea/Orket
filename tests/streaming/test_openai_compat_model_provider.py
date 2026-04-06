from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from orket.streaming.model_provider import (
    OpenAICompatModelStreamProvider,
    ProviderEventType,
    ProviderTurnRequest,
)


class _FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    async def __aenter__(self) -> _FakeStreamResponse:
        return self

    async def __aexit__(self, exc_type, exc: BaseException | None, tb) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line


class _FakeAsyncClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _ = args
        _ = kwargs

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc: BaseException | None, tb) -> None:
        return None

    def stream(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> _FakeStreamResponse:
        _ = headers
        _ = json
        assert method == "POST"
        assert path == "/chat/completions"
        return _FakeStreamResponse(
            [
                'data: {"choices":[{"delta":{}}]}',
                "data: [DONE]",
            ]
        )


def _event_payloads(events: list[Any], event_type: ProviderEventType) -> list[dict[str, Any]]:
    return [event.payload for event in events if event.event_type == event_type]


@pytest.mark.asyncio
async def test_openai_compat_stream_zero_deltas_emits_synthetic_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orket.streaming import model_provider

    monkeypatch.setenv("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", "true")
    monkeypatch.setattr(model_provider.httpx, "AsyncClient", _FakeAsyncClient)

    provider = OpenAICompatModelStreamProvider(model_id="test-model", base_url="http://example.test/v1")
    fallback_calls: list[dict[str, Any]] = []

    def fake_post_chat_completion_sync(headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        _ = headers
        fallback_calls.append(dict(payload))
        return {
            "choices": [{"message": {"content": ""}}],
            "usage": {"completion_tokens": 1},
        }

    monkeypatch.setattr(provider, "_post_chat_completion_sync", fake_post_chat_completion_sync)

    request = ProviderTurnRequest(input_config={"prompt": "hi", "max_tokens": 1}, turn_params={})
    events = [event async for event in provider.start_turn(request)]

    token_payloads = _event_payloads(events, ProviderEventType.TOKEN_DELTA)
    assert len(token_payloads) == 1
    assert token_payloads[0]["delta"] == ""
    assert token_payloads[0]["synthetic"] is True
    assert token_payloads[0]["reason"] == "empty_content_with_completion_tokens"
    assert token_payloads[0]["completion_tokens"] == 1

    stop_payloads = _event_payloads(events, ProviderEventType.STOPPED)
    assert len(stop_payloads) == 1
    assert stop_payloads[0]["stop_reason"] == "completed"

    assert len(fallback_calls) == 1
    assert fallback_calls[0]["stream"] is False


@pytest.mark.asyncio
async def test_openai_compat_non_stream_uses_completion_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", "false")
    provider = OpenAICompatModelStreamProvider(model_id="test-model", base_url="http://example.test/v1")

    def fake_post_chat_completion_sync(headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        _ = headers
        _ = payload
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"completion_tokens": 1},
        }

    monkeypatch.setattr(provider, "_post_chat_completion_sync", fake_post_chat_completion_sync)

    request = ProviderTurnRequest(input_config={"prompt": "hi", "max_tokens": 8}, turn_params={})
    events = [event async for event in provider.start_turn(request)]
    token_payloads = _event_payloads(events, ProviderEventType.TOKEN_DELTA)
    assert len(token_payloads) == 1
    assert token_payloads[0]["delta"] == "ok"
    assert "synthetic" not in token_payloads[0]


def test_openai_compat_extract_delta_supports_reasoning_and_text() -> None:
    reasoning_chunk = {"choices": [{"delta": {"reasoning_content": "thinking"}}]}
    text_chunk = {"choices": [{"delta": {"text": "answer"}}]}

    assert OpenAICompatModelStreamProvider._extract_delta(reasoning_chunk) == "thinking"
    assert OpenAICompatModelStreamProvider._extract_delta(text_chunk) == "answer"
