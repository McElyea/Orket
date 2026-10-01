"""Integration HTTP fallback behavior and unit delta parsing controls."""
from typing import Any

import pytest

from orket.application.services.model_stream_http_service import ModelStreamHttpService
from orket.streaming.model_provider import OpenAICompatModelStreamProvider, ProviderEventType, ProviderTurnRequest
from tests.helpers.observed_http_server import observed_http_server


def _event_payloads(events: list[Any], event_type: ProviderEventType) -> list[dict[str, Any]]:
    return [event.payload for event in events if event.event_type == event_type]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openai_compat_stream_zero_deltas_emits_synthetic_token(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", "true")

    async def response(request):
        if request[1]["stream"]:
            return 200, b'data: {"choices":[{"delta":{}}]}\n\ndata: [DONE]\n\n'
        return 200, {"choices": [{"message": {"content": ""}}], "usage": {"completion_tokens": 1}}

    async with observed_http_server(response) as server:
        provider = OpenAICompatModelStreamProvider(model_id="test-model", base_url=server[0],
            http_client_owner=ModelStreamHttpService(backend="openai_compat", base_url=server[0], timeout_s=3))
        events = [event async for event in provider.start_turn(ProviderTurnRequest(input_config={"prompt": "hi", "max_tokens": 1}))]
        token_payloads = _event_payloads(events, ProviderEventType.TOKEN_DELTA)
        assert len(token_payloads) == 1
        assert token_payloads[0]["delta"] == ""
        assert token_payloads[0]["synthetic"] is True
        assert token_payloads[0]["reason"] == "empty_content_with_completion_tokens"
        assert token_payloads[0]["completion_tokens"] == 1
        stop_payloads = _event_payloads(events, ProviderEventType.STOPPED)
        assert len(stop_payloads) == 1 and stop_payloads[0]["stop_reason"] == "completed"
        assert len(server[1]) == 2 and [request[1]["stream"] for request in server[1]] == [True, False]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openai_compat_non_stream_uses_completion_text(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", "false")

    async def response(_request):
        return 200, {"choices": [{"message": {"content": "ok"}}], "usage": {"completion_tokens": 1}}

    async with observed_http_server(response) as server:
        provider = OpenAICompatModelStreamProvider(model_id="test-model", base_url=server[0],
            http_client_owner=ModelStreamHttpService(backend="openai_compat", base_url=server[0], timeout_s=3))
        events = [event async for event in provider.start_turn(ProviderTurnRequest(input_config={"prompt": "hi", "max_tokens": 8}))]
        token_payloads = _event_payloads(events, ProviderEventType.TOKEN_DELTA)
        assert len(token_payloads) == 1 and token_payloads[0]["delta"] == "ok"
        assert "synthetic" not in token_payloads[0]
        assert len(server[1]) == 1 and server[1][0][1]["stream"] is False


@pytest.mark.unit
def test_openai_compat_extract_delta_supports_reasoning_and_text() -> None:
    reasoning_chunk = {"choices": [{"delta": {"reasoning_content": "thinking"}}]}
    text_chunk = {"choices": [{"delta": {"text": "answer"}}]}

    assert OpenAICompatModelStreamProvider._extract_delta(reasoning_chunk) == "thinking"
    assert OpenAICompatModelStreamProvider._extract_delta(text_chunk) == "answer"
