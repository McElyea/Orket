"""Integration: real HTTP route, application service, SDK provider and failing TCP provider."""
import asyncio

import pytest
from fastapi import FastAPI

from orket.application.services.extension_runtime_service import ExtensionRuntimeService
from orket.application.services.sdk_llm_provider import LocalModelCapabilityProvider
from orket.interfaces.routers.extension_runtime import build_extension_runtime_router
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_api_active_request_ownership import serving_api
from tests.integration.test_governed_ollama_reports import responder

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("failure", ["timeout", "unavailable"])
async def test_provider_failure_has_typed_http_response_and_one_attempt(tmp_path, failure):
    normal = responder()

    async def respond(request):
        if "/api/chat " in request[0]:
            if failure == "timeout":
                await asyncio.sleep(30.5)
            return 503, {"error": "PRIVATE_PROVIDER_DIAGNOSTIC"}
        return await normal(request)

    async with observed_http_server(respond, allow_disconnect=True) as (endpoint, requests):
        provider = await asyncio.to_thread(LocalModelCapabilityProvider, model="llama3.2:3b",
            temperature=0, seed=None, timeout=30, provider="ollama",
            environment={"ORKET_LLM_OLLAMA_HOST": endpoint, "ORKET_DISABLE_SANDBOX": "1"})
        try:
            service = await asyncio.to_thread(ExtensionRuntimeService, project_root=tmp_path, model_provider=provider)
            app = FastAPI()
            app.state.api_runtime_context = service
            app.include_router(build_extension_runtime_router(service_getter=lambda: service))
            async with serving_api(app) as client:
                response = await client.post("/extensions/test/runtime/llm/generate",
                    json={"user_message": "hello", "max_tokens": 256}, timeout=40)
            expected = "TIMEOUT" if failure == "timeout" else "UNAVAILABLE"
            assert response.status_code == (504 if failure == "timeout" else 503), response.text
            assert response.json()["detail"]["code"] == "E_EXTENSION_MODEL_PROVIDER_" + expected
            assert "PRIVATE_PROVIDER_DIAGNOSTIC" not in response.text
            assert len([1 for first, _ in requests if "/api/chat " in first]) == 1
        finally:
            await asyncio.to_thread(provider.close)
        assert not provider.is_available()
