"""Integration: real extension HTTP/SDK path and observed Ollama request bytes."""
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_api_active_request_ownership import serving_api

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROUTE = "/v1/extensions/orket.test/runtime/llm/generate"


@asynccontextmanager
async def ollama_api(tmp_path, monkeypatch, *, version="0.24.0", capacity=131072, host_context=None):
    async def respond(request):
        first, payload = request
        path = first.split()[1]
        if path == "/api/tags":
            return 200, {"models": [{"name": model} for model in
                                   (DEFAULT_LOCAL_MODEL, "llama3.2:3b", "unknown:latest")]}
        if path == "/api/version":
            return 200, {"version": version}
        if path == "/api/show":
            return 200, {"model_info": {"general.architecture": "llama", "llama.context_length": capacity}}
        if path == "/api/chat":
            return 200, {"message": {"role": "assistant", "content": "PELICAN"}, "done": True,
                         "done_reason": "stop", "prompt_eval_count": 40, "eval_count": 3}
        return 404, {"error": "unexpected endpoint"}

    async with observed_http_server(respond) as (endpoint, requests):
        if host_context is not None:
            source = Path("orket/runtime/config/local_prompt_profiles.json")
            registry = json.loads(await asyncio.to_thread(source.read_bytes))
            for entry in registry["profiles"]:
                if entry["profile"]["profile_id"].startswith("ollama."):
                    entry["profile"]["context_budget_tokens"] = host_context
            path = tmp_path / "profiles.json"
            await asyncio.to_thread(path.write_text, json.dumps(registry), encoding="utf-8")
            monkeypatch.setenv("ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH", str(path))
        for key, value in {"ORKET_DISABLE_SANDBOX": "1", "ORKET_API_KEY": "bt0-local-test-key",
                           "ORKET_LLM_PROVIDER": "ollama", "ORKET_LLM_OLLAMA_HOST": endpoint,
                           "ORKET_DURABLE_ROOT": str(tmp_path / ".orket/durable"),
                           "ORKET_OUTWARD_PIPELINE_DB_PATH": str(tmp_path / "outward.db")}.items():
            monkeypatch.setenv(key, value)
        app = create_api_app(CompositionConfig(project_root=tmp_path))
        async with serving_api(app) as client:
            yield client, requests
        context = app.state.api_runtime_context
        assert context.closed and not context.extension_runtime_service._model_provider.is_available()


def generation_body(*, override, content):
    body = dict(system_prompt="Answer the question.", user_message=content, max_tokens=16, temperature=0)
    if override:
        body.update(provider="ollama", model="llama3.2:3b")
    return body


@pytest.mark.parametrize("override", [False, True], ids=["default", "override"])
async def test_extension_ollama_sends_full_prompt_with_context_and_guards(tmp_path, monkeypatch, override):
    content = "The secret word is PELICAN.\nWhat is the secret word?"
    async with ollama_api(tmp_path, monkeypatch) as (client, requests):
        response = await client.post(ROUTE, json=generation_body(override=override, content=content))
        assert response.status_code == 200 and response.json()["text"] == "PELICAN", response.text
    chats = [payload for first, payload in requests if "/api/chat " in first]
    assert len(chats) == 1
    assert chats[0]["messages"][-1]["content"] == content
    assert chats[0]["options"]["num_ctx"] == 8192
    assert chats[0]["options"]["num_predict"] == 16
    assert chats[0]["truncate"] is False and chats[0]["shift"] is False


@pytest.mark.parametrize("override", [False, True], ids=["default", "override"])
@pytest.mark.parametrize("filler", ["filler\n" * 12000, "filler\n" * 72000, "東京" * 1500],
                         ids=["84kb", "504kb", "utf8-bytes"])
async def test_extension_ollama_refuses_oversized_input_without_chat(tmp_path, monkeypatch, override, filler):
    content = "The secret word is PELICAN.\n" + filler + "What is the secret word?"
    async with ollama_api(tmp_path, monkeypatch) as (client, requests):
        response = await client.post(ROUTE, json=generation_body(override=override, content=content))
        assert response.status_code == 400, response.text
        assert response.json()["detail"]["code"] == "E_MODEL_INPUT_BUDGET", response.text
        assert response.json()["detail"]["ok"] is False
    assert not any("/api/chat " in first for first, _ in requests)


@pytest.mark.parametrize("defect,expected", [
    ("old_server", "E_OLLAMA_TRUNCATION_GUARD_UNAVAILABLE"),
    ("model_capacity", "E_OLLAMA_CONTEXT_LIMIT"),
    ("missing_capacity", "E_OLLAMA_CONTEXT_LIMIT"),
    ("unknown_profile", "E_LOCAL_PROMPT_PROFILE_REQUIRED"),
    ("output_ceiling", "E_MODEL_OUTPUT_LIMIT"),
    ("system_prompt", "E_MODEL_INPUT_BUDGET"),
])
async def test_extension_ollama_refuses_unsafe_generation(tmp_path, monkeypatch, defect, expected):
    monkeypatch.setenv("ORKET_LOCAL_PROMPTING_MODE", "shadow")  # Shadow must not bypass input safety.
    options = {"version": "0.23.0"} if defect == "old_server" else {}
    if defect in {"model_capacity", "missing_capacity"}:
        options["capacity"] = 1024 if defect == "model_capacity" else None
    body = generation_body(override=True, content="Return PELICAN.")
    if defect == "unknown_profile":
        body["model"] = "unknown:latest"
    if defect == "output_ceiling":
        body["max_tokens"] = 8192
    if defect == "system_prompt":
        body["system_prompt"] = "system " * 2000
    async with ollama_api(tmp_path, monkeypatch, **options) as (client, requests):
        response = await client.post(ROUTE, json=body)
        assert response.status_code == 400, response.text
        assert response.json()["detail"]["code"] == expected, response.text
        assert response.json()["detail"]["ok"] is False
    assert not any("/api/chat " in first for first, _ in requests)


async def test_extension_ollama_honors_larger_explicit_host_context(tmp_path, monkeypatch):
    content = "The secret word is PELICAN.\n" + "filler\n" * 2400 + "What is the secret word?"
    async with ollama_api(tmp_path, monkeypatch, host_context=32768) as (client, requests):
        response = await client.post(ROUTE, json=generation_body(override=True, content=content))
        assert response.status_code == 200, response.text
    chat = next(payload for first, payload in requests if "/api/chat " in first)
    assert chat["messages"][-1]["content"] == content
    assert chat["options"]["num_ctx"] == 32768 and chat["truncate"] is False and chat["shift"] is False
