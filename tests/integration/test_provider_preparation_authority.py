"""Layer: integration. Actual HTTP clients cannot bypass application preparation policy."""
from contextlib import asynccontextmanager

import httpx
import pytest

from orket.application.services.local_model_factory import (
    create_local_model_provider_async,
)
from orket.exceptions import ModelConnectionError
from tests.helpers.observed_http_server import observed_http_server

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class DerivedClient(httpx.AsyncClient):
    """A real HTTP client with a distinct type, without changing transport behavior."""


@asynccontextmanager
async def observed_http_provider():
    async def response_for_request(request):
        first, _ = request
        payload = ({"data": [{"id": "fixture"}]} if first.startswith("GET /v1/models ") else
                   {"choices": [{"message": {"content": "observed"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        return 200, payload

    async with observed_http_server(response_for_request) as (url, requests):
        yield url + "/v1", requests


@pytest.mark.parametrize("client_kind", ["ordinary-client", "derived-client", "forwarding-mock-client"])
@pytest.mark.parametrize("quarantined", [False, True], ids=["admitted", "quarantined"])
async def test_real_inference_client_type_cannot_bypass_preparation(client_kind, quarantined):
    environment = {"ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL": "0",
                   "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL": "0"}
    if quarantined:
        environment["ORKET_PROVIDER_QUARANTINE"] = "openai_compat"
    async with observed_http_provider() as (url, requests):
        provider = (await create_local_model_provider_async("fixture", provider="openai_compat", base_url=url,
                                               timeout=5, connect_timeout_seconds=1, environment=environment))
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
