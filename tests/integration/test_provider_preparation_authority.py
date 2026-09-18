"""Layer: integration. Actual HTTP clients cannot bypass application preparation policy."""
import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import pytest

from orket.application.services.local_model_factory import create_local_model_provider
from orket.exceptions import ModelConnectionError

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class DerivedClient(httpx.AsyncClient):
    """A real HTTP client with a distinct type, without changing transport behavior."""


@asynccontextmanager
async def observed_http_provider():
    requests, owners, errors = [], set(), []

    async def respond(reader, writer):
        owner = asyncio.current_task()
        owners.add(owner)
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            first, *headers = head.decode().split("\r\n")
            length = next((int(h.split(":", 1)[1]) for h in headers if h.lower().startswith("content-length:")), 0)
            body = await reader.readexactly(length)
            requests.append((first, json.loads(body) if body else None))
            payload = ({"data": [{"id": "fixture"}]} if first.startswith("GET /v1/models ") else
                       {"choices": [{"message": {"content": "observed"}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
            content = json.dumps(payload).encode()
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n" +
                         f"Content-Length: {len(content)}\r\nConnection: close\r\n\r\n".encode() + content)
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError, ValueError) as exc:
            errors.append(repr(exc))
        finally:
            writer.close()
            await writer.wait_closed()
            owners.remove(owner)

    server = await asyncio.start_server(respond, "127.0.0.1", 0)
    try:
        yield f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/v1", requests
    finally:
        server.close()
        await server.wait_closed()
        if owners:
            await asyncio.wait_for(asyncio.gather(*owners), timeout=5)
        assert not owners and not errors


@pytest.mark.parametrize("client_kind", ["ordinary-client", "derived-client", "forwarding-mock-client"])
@pytest.mark.parametrize("quarantined", [False, True], ids=["admitted", "quarantined"])
async def test_real_inference_client_type_cannot_bypass_preparation(client_kind, quarantined):
    environment = {"ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL": "0",
                   "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL": "0"}
    if quarantined:
        environment["ORKET_PROVIDER_QUARANTINE"] = "openai_compat"
    async with observed_http_provider() as (url, requests):
        provider = create_local_model_provider("fixture", provider="openai_compat", base_url=url,
                                               timeout=5, connect_timeout_seconds=1, environment=environment)
        transport = None
        try:
            if client_kind != "ordinary-client":
                await provider.client.aclose()
                if client_kind == "derived-client":
                    provider.client = DerivedClient(base_url=url, timeout=5)
                else:
                    transport = httpx.AsyncHTTPTransport()
                    provider.client = httpx.AsyncClient(base_url=url, timeout=5,
                        transport=httpx.MockTransport(transport.handle_async_request))
            if quarantined:
                with pytest.raises(ModelConnectionError, match="quarantined_provider"):
                    await provider.complete([{"role": "user", "content": "hello"}])
                assert requests == [], "Quarantine must refuse before inventory or inference HTTP"
                assert provider._runtime_target is None
            else:
                result = await provider.complete([{"role": "user", "content": "hello"}])
                assert result.content == "observed"
                assert [first.split(" ")[:2] for first, _ in requests] == [
                    ["GET", "/v1/models"], ["POST", "/v1/chat/completions"]]
                assert result.raw["runtime_target"]["status"] == "OK"
                assert result.raw["runtime_target"]["model_id"] == requests[-1][1]["model"] == "fixture"
        finally:
            await provider.close()
            if transport is not None:
                await transport.aclose()
            assert provider.client.is_closed
