"""Real loopback provider requests and actual constructor observations for stream input admission."""
from __future__ import annotations

import asyncio
import os
import threading
from copy import deepcopy

from orket.streaming.model_provider import OpenAICompatModelStreamProvider
from orket.workloads import model_stream_v1 as workload


def seed_roots(root):
    first, other = root / "first", root / "other"
    for path, model in ((first, "fixture"), (other, "changed")):
        (path / "models").mkdir(parents=True)
        (path / "models" / (model + ".gguf")).write_bytes(b"local catalog fixture; no model inference")
    return first, other


def configure(monkeypatch, first, address, case):
    for key in tuple(os.environ):
        if key.lower() in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"} or key in {
            "SSL_CERT_FILE", "SSL_CERT_DIR", "SSLKEYLOGFILE"}:
            monkeypatch.delenv(key, raising=False)
    values = {"ORKET_MODEL_STREAM_PROVIDER": "real", "ORKET_MODEL_STREAM_REAL_PROVIDER":
        "llama_cpp" if case == "resolver-context" else "openai_compat",
        "ORKET_MODEL_STREAM_OPENAI_BASE_URL": address + "/v1", "ORKET_LLM_LLAMA_CPP_BASE_URL": address + "/v1",
        "ORKET_MODEL_STREAM_OPENAI_API_KEY": "fixture-original-key", "ORKET_MODEL_STREAM_REAL_TIMEOUT_S": "8",
        "ORKET_MODEL_STREAM_TURN_TIMEOUT_S": "8", "ORKET_MODEL_STREAM_OPENAI_USE_STREAM": "false",
        "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL": "false", "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL": "false",
        "ORKET_PROVIDER_QUARANTINE": "", "ORKET_PROVIDER_MODEL_QUARANTINE": "",
        "ORKET_LLAMA_CPP_GGUF_MODEL_ROOT": "models"}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(first)


def input_values(case):
    return {"model_id": "absent" if case == "empty-target" else "fixture",
        "messages": [{"role": "user", "content": "original request"}], "max_tokens": 8,
        "metadata": {"labels": ["original"]}}, {"metadata": {"route": ["original"]}}


def install_observers(monkeypatch, state, case):
    create, start = OpenAICompatModelStreamProvider.__init__, OpenAICompatModelStreamProvider.start_turn
    post, resolve = OpenAICompatModelStreamProvider._post_chat_completion_sync, workload.resolve_provider_runtime_target

    def constructed(owner, **options):
        create(owner, **options)
        state["constructor"] = {"model_id": options["model_id"], "base_url": options["base_url"],
            "timeout_s": options.get("timeout_s"), "api_key_original": options.get("api_key") == "fixture-original-key"}

    def started(owner, request):
        state["request"] = request.model_dump()
        return start(owner, request)

    def posted(owner, headers, payload):
        state["post_thread"] = threading.get_ident()
        try:
            return post(owner, headers, payload)
        finally:
            state["post_finished"].set()

    async def resolved(**options):
        if case == "resolver-context":
            state["arrived"].set()
            await asyncio.wait_for(state["release"].wait(), 5)
        target = await resolve(**options)
        state["target"] = target.to_payload()
        return target

    monkeypatch.setattr(OpenAICompatModelStreamProvider, "__init__", constructed)
    monkeypatch.setattr(OpenAICompatModelStreamProvider, "start_turn", started)
    monkeypatch.setattr(OpenAICompatModelStreamProvider, "_post_chat_completion_sync", posted)
    monkeypatch.setattr(workload, "resolve_provider_runtime_target", resolved)


async def response(request, state, case, *, alternate=False):
    first, body = request
    if first.startswith("GET /v1/models "):
        if not alternate and case != "resolver-context":
            state["arrived"].set()
            await asyncio.wait_for(state["release"].wait(), 5)
        return 200, {"data": [{"id": "changed" if alternate else "fixture"}]}
    assert first.startswith("POST /v1/chat/completions ")
    if case in {"inference-timeout", "turn-timeout"}:
        # Exceeds the mutated one-second budget, remains below the admitted eight seconds.
        await asyncio.sleep(1.3)
    return 200, {"choices": [{"message": {"content": body["messages"][0]["content"]}}],
                 "usage": {"completion_tokens": 1}}


def mutate(monkeypatch, other, alternate, case, input_config, turn_params):
    if case == "request":
        input_config["messages"][0]["content"] = "changed request"
        input_config["metadata"]["labels"].append("changed")
        turn_params["metadata"]["route"].append("changed")
    elif case == "api-key":
        monkeypatch.setenv("ORKET_MODEL_STREAM_OPENAI_API_KEY", "fixture-changed-key")
    elif case == "inference-timeout":
        monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_TIMEOUT_S", "1")
    elif case == "turn-timeout":
        monkeypatch.setenv("ORKET_MODEL_STREAM_TURN_TIMEOUT_S", "1")
    elif case == "resolver-context":
        monkeypatch.chdir(other)
        monkeypatch.setenv("ORKET_LLM_LLAMA_CPP_BASE_URL", alternate + "/v1")


def snapshot_inputs(input_config, turn_params):
    return deepcopy({"input_config": input_config, "turn_params": turn_params})
