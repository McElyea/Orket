"""Integration: builtin iterator lifetime over controlled real loopback HTTP."""
from __future__ import annotations

import asyncio
import json

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.interactions.context import InteractionContext
from orket.application.services.model_stream_http_service import ModelStreamHttpService
from orket.core.contracts.interaction_stream import StreamEventType
from orket.streaming.model_provider import OpenAICompatModelStreamProvider
from orket.workloads import model_stream_v1 as workload
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_api_active_request_ownership import serving_api
from tests.integration.test_api_interaction_lifetime import build_app

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class ObservedProvider(OpenAICompatModelStreamProvider):
    """Retain the actual iterator so implicit GC cannot stand in for owned close."""

    def __init__(self, url, marker, *, failure=None):
        super().__init__(model_id="fixture", base_url=url, timeout_s=3, http_client_owner=ModelStreamHttpService(
            backend="openai_compat", base_url=url, timeout_s=3))
        self.marker, self.failure = marker, failure
        self.closing, self.release = asyncio.Event(), asyncio.Event()
        self.iterator = None
        self.provider_closed = False

    async def aclose(self):
        self.provider_closed = True

    def start_turn(self, request):
        self.iterator = self._observed(request)
        return self.iterator

    async def _observed(self, request):
        native = super().start_turn(request)
        try:
            async for event in native:
                yield event
        finally:
            try:
                await native.aclose()
            finally:
                self.closing.set()
                await self.release.wait()
                await run_owned_thread(lambda: self.marker.write_text("closed", encoding="utf-8"),
                                       label="test-stream-close-observation")
                if self.failure is not None:
                    raise self.failure


def context(emit, commits):
    async def commit(intent):
        commits.append(intent)

    return InteractionContext(session_id="fixture-session", turn_id="fixture-turn", session_params={},
        packet1_context_envelope={}, packet1_provider_lineage=[], emit=emit,
        cancel_event=asyncio.Event(), commit_sink=commit)


def configure(monkeypatch, url, marker, failure=None):
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "real")
    monkeypatch.setenv("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", "true")
    provider = ObservedProvider(url, marker, failure=failure)

    async def build(**_inputs):
        return provider

    monkeypatch.setattr(workload, "_build_real_provider", build)
    return provider


async def response(_request):
    return 200, b'data: {"choices":[{"delta":{"content":"observed"}}]}\n\ndata: [DONE]\n\n'


async def settle_fixture(task, provider):
    provider.release.set()
    if not task.done():
        task.cancel()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    if provider.iterator is not None:
        try:
            await provider.iterator.aclose()
        except OSError:
            assert provider.failure is not None


@pytest.mark.parametrize("terminal", ["completed", "provider-error", "emit-error"])
@pytest.mark.parametrize("close_failure", [False, True, "timeout"])
async def test_builtin_closes_stream_before_result_or_commit(tmp_path, monkeypatch, terminal, close_failure):
    marker = tmp_path / "iterator-close.txt"
    commits, emitted = [], []
    primary = ValueError("controlled event sink failure")
    failure_type = TimeoutError if close_failure == "timeout" else OSError
    native_failure = failure_type("controlled close failure") if close_failure else None

    async def emit(kind, payload):
        emitted.append((kind, payload))
        if terminal == "emit-error" and kind == StreamEventType.TOKEN_DELTA:
            raise primary
        return True

    async def selected_response(request):
        return (500, {"error": "controlled refusal"}) if terminal == "provider-error" else await response(request)

    async with observed_http_server(selected_response, content_type="text/event-stream") as server:
        provider = configure(monkeypatch, server[0], marker, native_failure)
        provider.release.set()
        task = asyncio.create_task(workload.run_model_stream_v1(
            input_config={"prompt": "fixture", "max_tokens": 1}, turn_params={},
            interaction_context=context(emit, commits)))
        try:
            result, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            assert len(server[1]) == 1
            assert await asyncio.to_thread(marker.is_file), "workload returned before explicit iterator close"
            assert not provider._canceled and not provider.provider_closed
            if close_failure:
                assert result is native_failure and not commits
                if terminal == "emit-error":
                    assert result.__context__ is primary
            elif terminal == "emit-error":
                assert result is primary and not commits
            elif terminal == "provider-error":
                assert result["request_cancel_turn"] == 1 and commits[0].type == "decision"
            else:
                assert result == {"post_finalize_wait_ms": 0} and commits[0].type == "turn_finalize"
        finally:
            await settle_fixture(task, provider)


@pytest.mark.parametrize("close_failure", [False, True, "timeout"])
@pytest.mark.parametrize("stop", ["caller", "deadline"])
async def test_builtin_retains_close_through_repeated_cancellation(tmp_path, monkeypatch, close_failure, stop):
    marker = tmp_path / "iterator-close.txt"
    commits, token = [], asyncio.Event()
    failure_type = TimeoutError if close_failure == "timeout" else OSError
    native_failure = failure_type("controlled close failure") if close_failure else None

    async def emit(kind, _payload):
        if kind == StreamEventType.TOKEN_DELTA:
            token.set()
            await asyncio.Event().wait()
        return True

    async with observed_http_server(response, content_type="text/event-stream") as server:
        provider = configure(monkeypatch, server[0], marker, native_failure)
        if stop == "deadline":
            monkeypatch.setenv("ORKET_MODEL_STREAM_TURN_TIMEOUT_S", "1")
        task = asyncio.create_task(workload.run_model_stream_v1(
            input_config={"prompt": "fixture", "max_tokens": 1}, turn_params={},
            interaction_context=context(emit, commits)))
        closing_waiter = asyncio.create_task(provider.closing.wait())
        try:
            await asyncio.wait_for(token.wait(), 5)
            if stop == "caller":
                task.cancel("first stream interruption")
            done, _ = await asyncio.wait([task, closing_waiter],
                                         timeout=2, return_when=asyncio.FIRST_COMPLETED)
            assert provider.closing.is_set(), "cancellation returned without starting iterator close"
            assert task not in done and not task.done(), "close was abandoned"
            if stop == "caller":
                task.cancel("second stream interruption")
            await asyncio.sleep(0)
            assert not task.done() and not commits
            provider.release.set()
            result, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            assert await asyncio.to_thread(marker.is_file) and not provider._canceled
            if close_failure:
                assert result is native_failure
            elif stop == "caller":
                assert isinstance(result, asyncio.CancelledError)
            else:
                assert result["request_cancel_turn"] == 1
                assert len(commits) == 1 and commits[0].ref == "fail_closed:provider_error:provider_turn_timeout:1.0s"
            if stop == "caller" or close_failure:
                assert not commits
        finally:
            await settle_fixture(task, provider)
            await asyncio.wait_for(closing_waiter, 5)


@pytest.mark.parametrize("close_failure", [False, True])
async def test_public_http_shutdown_retains_model_iterator(tmp_path, monkeypatch, close_failure):
    marker = tmp_path / "shutdown-close.txt"
    failure = OSError("controlled shutdown close failure") if close_failure else None
    async with observed_http_server(response, content_type="text/event-stream") as server:
        provider = configure(monkeypatch, server[0], marker, failure)
        app = build_app(tmp_path, monkeypatch)
        closing = None
        async with serving_api(app) as client:
            runtime = app.state.api_runtime_context
            try:
                session = (await client.post("/v1/interactions/sessions", json={})).json()["session_id"]
                admitted = await client.post(f"/v1/interactions/{session}/turns", json={
                    "workload_id": "model_stream_v1", "input_config": {"prompt": "fixture", "max_tokens": 1}})
                assert admitted.status_code == 200, admitted.text
                turn = admitted.json()["turn_id"]
                await asyncio.wait_for(provider.closing.wait(), 5)
                assert (await asyncio.wait_for(client.get("/v1/system/heartbeat"), 0.5)).status_code == 200
                closing = asyncio.create_task(runtime.close())
                for _ in range(3):
                    await asyncio.sleep(0.01)
                    closing.cancel()
                assert not closing.done() and not runtime.closed
                path = tmp_path / "workspace/interactions" / session / turn / "authority_commit.json"
                assert not await asyncio.to_thread(path.exists)
                provider.release.set()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(closing, 5)
                assert runtime.closed and not provider._canceled
                assert runtime.active_background_task_count == runtime.active_request_count == 0
                assert await asyncio.to_thread(marker.is_file)
                payload = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
                assert payload["intents"] and all(intent["type"] == "decision" for intent in payload["intents"])
                if close_failure:
                    assert "controlled shutdown close failure" in str(payload)
            finally:
                provider.release.set()
                if closing is not None:
                    await asyncio.gather(closing, return_exceptions=True)
