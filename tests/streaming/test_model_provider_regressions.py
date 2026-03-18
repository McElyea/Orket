from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest

from orket.streaming.model_provider import (
    OllamaModelStreamProvider,
    ProviderEventType,
    ProviderTurnRequest,
    StubModelStreamProvider,
)


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_stub_model_provider_preserves_pre_cancel_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = StubModelStreamProvider()
    monkeypatch.setattr("orket.streaming.model_provider.uuid.uuid4", lambda: SimpleNamespace(hex="abcdefabcdef123456"))

    await provider.cancel("provider-turn-abcdefabcdef")
    events = [event async for event in provider.start_turn(ProviderTurnRequest())]

    assert [event.event_type for event in events] == [
        ProviderEventType.SELECTED,
        ProviderEventType.LOADING,
        ProviderEventType.READY,
        ProviderEventType.STOPPED,
    ]
    assert events[-1].payload["stop_reason"] == "canceled"


@pytest.mark.asyncio
async def test_ollama_model_provider_uses_longer_stream_timeout_than_connect_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeAsyncClient:
        def __init__(self, host: str | None = None) -> None:
            self.host = host

        async def chat(self, *, model: str, messages: list[dict[str, str]], options: dict[str, object], stream: bool):
            assert model == "fake-model"
            assert isinstance(messages, list)
            assert isinstance(options, dict)
            assert stream is True

            async def _stream():
                yield {"message": {"content": "hello"}}
                await asyncio.sleep(0.7)
                yield {"message": {"content": "world"}}

            return _stream()

    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(AsyncClient=_FakeAsyncClient))

    provider = OllamaModelStreamProvider(model_id="fake-model", timeout_s=1.0)
    events = [event async for event in provider.start_turn(ProviderTurnRequest(input_config={"prompt": "hi"}))]

    assert provider._connect_timeout_s == 1.0
    assert provider._stream_timeout_s == 3.0
    assert [event.payload["delta"] for event in events if event.event_type == ProviderEventType.TOKEN_DELTA] == [
        "hello",
        "world",
    ]
