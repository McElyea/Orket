"""Standalone provider calls retain real HTTP retries and their captured log inputs."""
from __future__ import annotations

import asyncio
import json
from contextlib import nullcontext

import httpx
import pytest

from orket.adapters.llm.llama_cpp_render_verification import QWEN38_TEXT_TEMPLATE_PATH, expected_text_render
from orket.adapters.observability.logging_context import selected_logging
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.exceptions import ModelConnectionError
from orket.logging import bind_logging, prepare_logging, settle_log_write_frontier
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.script_provider_logging_cases import (
    CALLERS,
    assert_result,
    invoke_script,
    model_for,
    response_content,
)
from tests.integration.test_provider_inference_ownership import observe_resources

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

def _response(caller, monkeypatch, later, headers, posts, template, recover):
    model = model_for(caller)
    async def respond(request):
        headers.clear()
        path = request[0].split()[1]
        if path == "/props":
            return 200, {"chat_template": template, "model_alias": model,
                         "default_generation_settings": {"n_ctx": 32768}, "build_info": "controlled-HTTP-fixture"}
        if path == "/apply-template":
            return 200, {"prompt": expected_text_render(request[1]["messages"])}
        if path == "/tokenize":
            return 200, {"tokens": list(range(len(request[1]["content"].split())))}
        if request[0].startswith("GET "):
            return 200, {"data": [{"id": model}]}
        assert path == "/v1/chat/completions"
        posts.append(request)
        if len(posts) == 1:
            monkeypatch.chdir(later)
            monkeypatch.setenv("ORKET_TIMEZONE", "America/Phoenix")
        if len(posts) == 1 or not recover:
            # Conflicting real HTTP lengths force the provider's network retry path.
            headers.append(("Content-Length", "9999"))
        message = {"role": "assistant", "content": response_content(caller, len(posts) - 1)}
        return 200, {"model": model, "choices": [{"message": message, "finish_reason": "stop", "index": 0}]}
    return respond


@pytest.mark.parametrize("caller", CALLERS)
@pytest.mark.parametrize("recover", [False, True], ids=["exhausted", "recovered"])
async def test_standalone_provider_retry_keeps_real_logging(tmp_path, monkeypatch, record_property, caller, recover):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_TIMEZONE", "UTC")
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("ORKET_LOCAL_PROMPTING_MODE", "shadow")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    for key in ("ORKET_LLM_OPENAI_API_KEY", "ORKET_MODEL_STREAM_OPENAI_API_KEY",
                "ORKET_LLM_LLAMA_CPP_API_KEY", "ORKET_LLAMA_CPP_API_KEY"):
        monkeypatch.setenv(key, "")
    if caller.endswith("readiness"):
        # Exercise real catalog admission independently of host model installations.
        models = tmp_path / "models"
        await asyncio.to_thread(models.mkdir)
        await asyncio.to_thread(
            (models / (model_for(caller) + ".gguf")).write_bytes,
            b"admission inventory fixture; no model inference",
        )
        monkeypatch.setenv("ORKET_LLAMA_CPP_GGUF_MODEL_ROOT", str(models))
    later = tmp_path / "later"
    await asyncio.to_thread(later.mkdir)
    headers, posts = [], []
    template = await asyncio.to_thread(QWEN38_TEXT_TEMPLATE_PATH.read_text, encoding="utf-8")
    respond = _response(caller, monkeypatch, later, headers, posts, template, recover)
    resources, closed = observe_resources(monkeypatch)
    outer = await prepare_logging(LoggingInputs(tmp_path / "other", timezone_name="America/Phoenix"))
    async with observed_http_server(respond, response_headers=headers, allow_disconnect=True) as (url, requests):
        monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", url + "/v1")
        monkeypatch.setenv("ORKET_LLM_LLAMA_CPP_BASE_URL", url + "/v1")
        with bind_logging(outer) if recover else nullcontext():
            before = selected_logging(required=False)
            if recover or caller in {"guide", "judge"}:
                result = await invoke_script(caller, tmp_path, url)
                assert_result(caller, result, recover)
            else:
                with pytest.raises(ModelConnectionError, match="failed after 3 attempts"):
                    await invoke_script(caller, tmp_path, url)
            assert selected_logging(required=False) is before
    assert len(posts) >= 2 if recover else len(posts) == 3
    # The owner closes a transport directly and through its client; require every
    # real resource to settle, without inventing an exactly-once close contract.
    assert resources and set(resources) == set(closed)
    clients = [resource for resource in resources if isinstance(resource, httpx.AsyncClient)]
    assert clients and all(client.is_closed for client in clients)
    await asyncio.to_thread(settle_log_write_frontier)
    rows = [json.loads(line) for line in (await asyncio.to_thread(
        (tmp_path / "workspace/default/orket.log").read_text, encoding="utf-8")).splitlines()]
    events = [row for row in rows if row["event"] == "model_connection_retry"]
    assert len(events) == (1 if recover else 2)
    assert all(row["timestamp"].endswith("+00:00") for row in events)
    assert not await asyncio.to_thread((later / "workspace").exists)
    record_property("standalone_provider_logging", json.dumps({"caller": caller, "recovered": recover,
        "http_requests": len(requests), "events": events, "caller_restored": True,
        "closed_resources": len(set(closed)), "provider": "llama_cpp" if caller.endswith("readiness") else "openai_compat",
        "inference": "controlled HTTP responses; no model inference"}))
