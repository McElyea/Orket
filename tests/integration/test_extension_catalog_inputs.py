"""Layer: integration. Real loopback model inventory retains its admitted provider identity."""
import asyncio
import json
from contextlib import asynccontextmanager

import pytest

from orket.interfaces.api import create_api_app
from tests.integration.test_api_observation_ownership import _request

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@asynccontextmanager
async def _catalog_server(*, status=200):
    entered, release = asyncio.Event(), asyncio.Event()
    requests, tasks = [], set()

    async def handle(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        try:
            requests.append((await reader.readuntil(b"\r\n\r\n")).decode("ascii").splitlines()[0])
            entered.set()
            await release.wait()
            body = json.dumps({"data": [{"id": "fixture-model"}]}).encode()
            writer.write(f"HTTP/1.1 {status} Fixture\r\nContent-Length: {len(body)}\r\n"
                         "Content-Type: application/json\r\nConnection: close\r\n\r\n".encode() + body)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.remove(task)

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/v1", entered, release, requests
    finally:
        release.set()
        server.close()
        await server.wait_closed()
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks), 3)


async def test_catalog_failure_reports_admitted_provider_after_environment_rotation(tmp_path, monkeypatch, api_key_env):
    async with _catalog_server(status=503) as (url, entered, release, requests):
        monkeypatch.setenv("ORKET_LLM_PROVIDER", "llama_cpp")
        monkeypatch.setenv("ORKET_LLAMA_CPP_BASE_URL", url)
        app = create_api_app(project_root=tmp_path)
        request = asyncio.create_task(_request(app, "/v1/extensions/fixture/runtime/models", key="test-key"))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            monkeypatch.setenv("ORKET_LLM_PROVIDER", "openai_compat")
            release.set()
            response = await asyncio.wait_for(request, 3)
            assert response.status_code == 503, response.text
            assert response.json()["detail"]["requested_provider"] == "llama_cpp"
            assert requests == ["GET /v1/models HTTP/1.1"]
            record = json.loads(await asyncio.to_thread((tmp_path / "orket.log").read_text, encoding="utf-8"))
            assert record["event"] == "extension_runtime_model_catalog_unavailable"
            assert record["data"]["provider"] == "llama_cpp"
        finally:
            release.set()
            await asyncio.gather(request, return_exceptions=True)
            await app.state.api_runtime_context.close()


async def test_catalogs_keep_application_endpoints_after_environment_rotation(tmp_path, monkeypatch):
    async with _catalog_server() as first, _catalog_server() as second:
        apps = []
        for index, server in enumerate((first, second)):
            environment = {"ORKET_API_KEY": "expected", "ORKET_LLM_PROVIDER": "llama_cpp",
                           "ORKET_LLAMA_CPP_BASE_URL": server[0],
                           "ORKET_LLAMA_CPP_GGUF_MODEL_ROOT": str(tmp_path / "empty-models")}
            apps.append(create_api_app(project_root=tmp_path / str(index), environment=environment))
            environment["ORKET_LLAMA_CPP_BASE_URL"] = "http://127.0.0.1:1/v1"
            server[2].set()
        monkeypatch.setenv("ORKET_LLM_PROVIDER", "openai_compat")
        monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
        try:
            responses = await asyncio.wait_for(asyncio.gather(*[
                _request(app, "/v1/extensions/fixture/runtime/models") for app in apps
            ]), 3)
            for response, server in zip(responses, (first, second), strict=True):
                assert response.status_code == 200, response.text
                assert response.json()["requested_provider"] == "llama_cpp"
                assert response.json()["base_url"] == server[0]
                assert response.json()["models"] == ["fixture-model"]
                assert response.json()["default_model"] == "fixture-model"
                assert server[3] == ["GET /v1/models HTTP/1.1"]
        finally:
            await asyncio.gather(*(app.state.api_runtime_context.close() for app in apps))
