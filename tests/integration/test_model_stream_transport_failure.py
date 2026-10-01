"""Integration: partial real HTTP stream failure and cancellation during a pending response."""
import asyncio
from contextlib import asynccontextmanager

import pytest

from orket.core.contracts.interaction_stream import StreamEventType
from orket.workloads import model_stream_v1 as workload
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_model_stream_iterator_lifetime import context
from tests.integration.test_model_stream_transport_lifetime import configure, observed_clients

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@asynccontextmanager
async def broken_stream(backend):
    owners, requests = [], []

    async def respond(reader, writer):
        owners.append(asyncio.current_task())
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            length = next(int(line.split(b":", 1)[1]) for line in head.split(b"\r\n")
                          if line.lower().startswith(b"content-length:"))
            requests.append(await reader.readexactly(length))
            body = (b'{"message":{"role":"assistant","content":"partial"},"done":false}\n' if backend == "ollama"
                    else b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n')
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 10000\r\nConnection: close\r\n\r\n" + body)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(respond, "127.0.0.1", 0)
    try:
        yield f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}", requests
    finally:
        server.close()
        await server.wait_closed()
        await asyncio.wait_for(asyncio.gather(*owners), 5)


@pytest.mark.parametrize("backend", ["stream", "ollama"])
async def test_partial_http_body_fails_closed_after_real_token_and_cleanup(monkeypatch, backend):
    clients, _threads = observed_clients(monkeypatch)
    emitted, commits = [], []

    async def emit(kind, payload):
        emitted.append((kind, payload))
        return True

    async with broken_stream(backend) as server:
        provider = configure(monkeypatch, backend, server[0])
        result = await asyncio.wait_for(workload.run_model_stream_v1(
            input_config={"prompt": "fixture", "max_tokens": 8}, turn_params={},
            interaction_context=context(emit, commits)), 5)
        assert len(server[1]) == 1 and result == {"request_cancel_turn": 1, "post_finalize_wait_ms": 0}
        assert [payload["delta"] for kind, payload in emitted if kind == StreamEventType.TOKEN_DELTA] == ["partial"]
        assert len(commits) == 1 and commits[0].type == "decision"
        assert "peer closed connection without sending complete message body" in commits[0].ref
        assert "expected 10000" in commits[0].ref
        assert clients and all(client.is_closed for client in clients) and not provider._canceled


@pytest.mark.parametrize("backend", ["stream", "nonstream", "ollama"])
@pytest.mark.parametrize("stop", ["caller", "deadline"])
async def test_pending_real_http_response_is_closed_before_interrupted_return(monkeypatch, backend, stop):
    entered = asyncio.Event()
    clients, _threads = observed_clients(monkeypatch)
    commits = []

    async def response(_request):
        entered.set()
        # The fixture's None response waits for actual peer EOF; its context exit
        # joins that observer and therefore proves client-side connection release.
        return None

    async def emit(_kind, _payload):
        return True

    async with observed_http_server(response) as server:
        provider = configure(monkeypatch, backend, server[0])
        if stop == "deadline":
            monkeypatch.setenv("ORKET_MODEL_STREAM_TURN_TIMEOUT_S", "1")
        task = asyncio.create_task(workload.run_model_stream_v1(input_config={"prompt": "fixture"}, turn_params={},
            interaction_context=context(emit, commits)))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            if stop == "caller":
                for _ in range(3):
                    task.cancel()
                    await asyncio.sleep(0)
            outcome, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            if stop == "caller":
                assert isinstance(outcome, asyncio.CancelledError) and not commits
            else:
                assert outcome["request_cancel_turn"] == 1 and commits[0].type == "decision"
            assert clients and all(client.is_closed for client in clients) and not provider._canceled
        finally:
            task.cancel()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    assert len(server[1]) == 1
