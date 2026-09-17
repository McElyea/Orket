"""Real API/SDK/policy path with a controlled provider HTTP transport."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from orket.capabilities.sync_bridge import run_coro_sync
from tests.integration.test_api_active_request_ownership import serving_api
from tests.integration.test_extension_generation_api_lifetime import generation_app as generation_app


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_stop", [False, True])
# Layer: integration
async def test_api_preserves_generation_options_and_rejects_empty_stop(generation_app, invalid_stop):
    observed = []

    def respond(request):
        observed.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "controlled"}}]})

    provider = generation_app.state.api_runtime_context.extension_runtime_service._model_provider._provider
    await asyncio.to_thread(run_coro_sync, provider.client.aclose())
    # Keep API, SDK bridge and policy real; this transport is not live inference.
    provider.provider_name = "lmstudio"
    provider.client = httpx.AsyncClient(base_url="http://controlled.test/v1", transport=httpx.MockTransport(respond))
    async with serving_api(generation_app) as client:
        response = await client.post("/v1/extensions/orket.test/runtime/llm/generate", json={
            "user_message": "hello", "max_tokens": 512, "temperature": 0.0,
            "stop_sequences": [""] if invalid_stop else [" ", " END\n"]})
        if invalid_stop:
            assert response.status_code == 400 and observed == []
        else:
            assert response.status_code == 200 and response.json()["text"] == "controlled"
            assert len(observed) == 1 and observed[0]["max_tokens"] == 512
            assert observed[0]["temperature"] == 0.0 and observed[0]["stop"][:2] == [" ", " END\n"]
