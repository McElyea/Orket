"""Integration: admitted streaming transport construction and captured network inputs."""
import asyncio
import json
import threading

import httpx
import pytest

from orket.application.services.model_stream_http_service import ModelStreamHttpService
from orket.streaming.model_provider import OllamaModelStreamProvider, OpenAICompatModelStreamProvider
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_model_stream_transport_lifetime import configure, responder, run
from tests.integration.test_provider_http_environment import _ambient_proxy

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("backend", ["stream", "nonstream", "ollama"])
@pytest.mark.parametrize("failure", [False, True])
@pytest.mark.parametrize("cancel", [False, True])
async def test_held_native_construction_settles_before_workload_return(monkeypatch, backend, failure, cancel):
    entered, release = threading.Event(), threading.Event()
    native_failure = OSError("controlled native client construction failure") if failure else None
    create, close = httpx.AsyncClient.__init__, httpx.AsyncHTTPTransport.aclose
    transports, closed, clients = [], [], []
    native_transport = httpx.AsyncHTTPTransport.__init__

    def transport_created(transport, *args, **options):
        native_transport(transport, *args, **options)
        transports.append(transport)

    def held(client, *args, **options):
        entered.set()
        assert release.wait(5)
        if native_failure:
            raise native_failure
        create(client, *args, **options)
        clients.append(client)

    async def closed_transport(transport):
        await close(transport)
        closed.append(transport)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", held)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "__init__", transport_created)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "aclose", closed_transport)
    commits = []
    async with observed_http_server(responder(backend)) as server:
        configure(monkeypatch, backend, server[0])
        task = asyncio.create_task(run(commits))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            if cancel:
                for _ in range(3):
                    task.cancel()
                    await asyncio.sleep(0)
            assert not task.done() and not commits and not server[1]
            release.set()
            outcome, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            assert transports and all(transport in closed for transport in transports)
            assert all(client.is_closed for client in clients)
            if failure:
                assert outcome is native_failure and not commits
            elif cancel:
                assert isinstance(outcome, asyncio.CancelledError) and not commits
            else:
                assert outcome == {"post_finalize_wait_ms": 0} and commits[0].type == "turn_finalize"
            assert len(server[1]) == int(not cancel and not failure)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


def fixture_response(backend, marker):
    async def response(request):
        if backend == "ollama":
            return 200, (json.dumps({"model": "fixture", "message": {"role": "assistant", "content": marker},
                                    "done": True}) + "\n").encode()
        if request[1]["stream"]:
            return 200, ('data: ' + json.dumps({"choices": [{"delta": {"content": marker}}]}) + '\n\n').encode()
        return 200, {"choices": [{"message": {"content": marker}}]}
    return response


@pytest.mark.parametrize("backend", ["stream", "nonstream", "ollama"])
@pytest.mark.parametrize("mode", ["empty", "proxy", "bypass", "ambient"])
async def test_stream_http_uses_captured_policy_after_environment_mutation(monkeypatch, backend, mode):
    headers = {name: [] for name in ("origin", "supplied", "ambient")}
    async with (
        observed_http_server(fixture_response(backend, "origin"), request_headers=headers["origin"]) as origin,
        observed_http_server(fixture_response(backend, "supplied"), request_headers=headers["supplied"]) as supplied,
        observed_http_server(fixture_response(backend, "ambient"), request_headers=headers["ambient"]) as ambient,
    ):
        _ambient_proxy(monkeypatch, ambient[0])
        monkeypatch.setenv("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", str(backend == "stream"))
        monkeypatch.setenv("OLLAMA_API_KEY", "public-before-test-key")
        environment = None if mode == "ambient" else {
            "ORKET_MODEL_STREAM_OPENAI_USE_STREAM": str(backend == "stream")}
        if mode in {"proxy", "bypass"}:
            environment.update(HTTP_PROXY=supplied[0], NO_PROXY="127.0.0.1" if mode == "bypass" else "",
                               OLLAMA_API_KEY="public-captured-test-key")
        http = ModelStreamHttpService(backend="ollama" if backend == "ollama" else "openai_compat",
            base_url=origin[0], timeout_s=2, environment=environment)
        provider_class = OllamaModelStreamProvider if backend == "ollama" else OpenAICompatModelStreamProvider
        provider = provider_class(model_id="fixture", base_url=origin[0], http_client_owner=http)
        monkeypatch.setenv("HTTP_PROXY", "http://unreachable.invalid:1")
        monkeypatch.setenv("OLLAMA_API_KEY", "public-after-test-key")
        monkeypatch.setenv("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", str(backend != "stream"))
        if environment is not None:
            environment.update(HTTP_PROXY="http://unreachable.invalid:2", OLLAMA_API_KEY="public-mutated-test-key")
        from orket.streaming.model_provider import ProviderEventType, ProviderTurnRequest
        events = [event async for event in provider.start_turn(ProviderTurnRequest(input_config={"prompt": "fixture"}))]
        expected = "ambient" if mode == "ambient" else ("supplied" if mode == "proxy" else "origin")
        assert [event.payload["delta"] for event in events if event.event_type == ProviderEventType.TOKEN_DELTA] == [expected]
        selected = dict(origin=origin, supplied=supplied, ambient=ambient)[expected]
        assert sum(len(server[1]) for server in (origin, supplied, ambient)) == len(selected[1]) == 1
        if backend == "ollama":
            key = "public-before-test-key" if mode == "ambient" else (
                "public-captured-test-key" if mode in {"proxy", "bypass"} else None)
            assert headers[expected][0].get("authorization") == ("Bearer " + key if key else None)
        else:
            assert selected[1][0][1]["stream"] == (backend == "stream")
