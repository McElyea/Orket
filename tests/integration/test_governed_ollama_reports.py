"""Integration: public CLI/SDK/SQLite with observed native Ollama HTTP contracts."""
import asyncio
import json
import socket

import pytest

from orket_extension_sdk import canonical_digest_sha256
from tests.helpers.governed_agent_task import prepare_report_task, report_response
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_runtime_entrypoints import child

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def invoke(root, endpoint, paths):
    catalog, submission, inputs = paths
    code, output, error = await child(root, ["-m", "orket.cli", "agent", "run", "--catalog", str(catalog),
        "--submission", str(submission), "--inputs", str(inputs), "--db", str(root / "agent.sqlite3"),
        "--model", "llama3.2:3b", "--provider", "ollama", "--provider-base-url", endpoint,
        "--inventory-timeout-seconds", "1", "--json"])
    assert output, error
    return code, json.loads(output)


def responder(*, version="0.24.0", model_limit=131072, output=None, finish_reason="stop"):
    async def respond(request):
        first, payload = request
        path = first.split()[1]
        if path == "/api/tags":
            return 200, {"models": [{"name": "llama3.2:3b"}]}
        if path == "/api/version":
            return 200, {"version": version}
        if path == "/api/show":
            return 200, {"model_info": {"general.architecture": "llama", "llama.context_length": model_limit}}
        if path == "/api/chat":
            return 200, {"message": {"role": "assistant", "content": output or json.dumps(report_response())},
                         "done": True, "done_reason": finish_reason, "prompt_eval_count": 650, "eval_count": 90}
        return 404, {"error": "unexpected endpoint"}
    return respond


async def test_report_uses_selected_http_inventory_explicit_context_and_no_truncation(tmp_path):
    paths = await asyncio.to_thread(prepare_report_task, tmp_path)
    async with observed_http_server(responder()) as (endpoint, requests):
        code, result = await invoke(tmp_path, endpoint, paths)
    assert code == 0 and result["ok"], result
    chats = [payload for first, payload in requests if "/api/chat " in first]
    assert len(chats) == 1
    assert chats[0]["options"]["num_ctx"] == 5120  # example's 4096 input + 1024 output
    assert chats[0]["options"]["num_predict"] == 1024
    assert chats[0]["truncate"] is False and chats[0]["shift"] is False
    assert chats[0]["format"]["required"] == ["sections", "source_refs", "limitations", "advisory"]
    assert chats[0]["format"]["properties"]["sections"]["required"] == ["summary"]
    assert result["model_targets"]["reporter"]["inventory_source"] == "http_api_tags"
    assert "Example shape" not in chats[0]["messages"][0]["content"]


async def test_unavailable_ollama_is_typed_without_cli_or_logging_failure(tmp_path):
    paths = await asyncio.to_thread(prepare_report_task, tmp_path)
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        code, result = await invoke(tmp_path, f"http://127.0.0.1:{held.getsockname()[1]}", paths)
    assert code == 1
    assert result["error"].startswith("E_AGENT_LOCAL_INVENTORY_UNAVAILABLE:ollama:"), result
    assert not (tmp_path / "agent.sqlite3").exists()


@pytest.mark.parametrize("defect", ["large_input", "output_cap", "old_server", "model_context"])
async def test_preflight_refuses_without_generation_and_retains_specific_reason(tmp_path, defect):
    paths = await asyncio.to_thread(prepare_report_task, tmp_path)
    if defect == "large_input":
        payload = json.loads(await asyncio.to_thread(paths[2].read_bytes))
        item = payload[-1]
        item["content"] = "東京" * 3000
        item["digest"] = "sha256:" + canonical_digest_sha256(item["content"])
        item["encoded_bytes"] = len(json.dumps(item["content"], ensure_ascii=False, separators=(",", ":")).encode())
        await asyncio.to_thread(paths[2].write_text, json.dumps(payload), encoding="utf-8")
    if defect == "output_cap":
        payload = json.loads(await asyncio.to_thread(paths[1].read_bytes))
        payload["requested_model_profiles"][0]["max_output_tokens"] = 4096
        for name in ("run_budget", "iteration_budget"):
            budget = payload[name]
            budget["output_tokens"] = 4096
            budget.pop("snapshot_digest")
            budget["snapshot_digest"] = "sha256:" + canonical_digest_sha256(budget)
        await asyncio.to_thread(paths[1].write_text, json.dumps(payload), encoding="utf-8")
    respond = responder(version="0.23.0" if defect == "old_server" else "0.24.0",
                        model_limit=1024 if defect == "model_context" else 131072)
    async with observed_http_server(respond) as (endpoint, requests):
        code, result = await invoke(tmp_path, endpoint, paths)
    assert code == 1 and not result["ok"], result
    assert not any("/api/chat " in first for first, _ in requests)
    expected = {"large_input": "E_MODEL_INPUT_BUDGET", "output_cap": "E_MODEL_OUTPUT_LIMIT",
                "old_server": "E_OLLAMA_TRUNCATION_GUARD_UNAVAILABLE", "model_context": "E_OLLAMA_CONTEXT_LIMIT"}[defect]
    calls = result["iterations"][0]["model_calls"]
    assert calls[0]["normalized_reason"].startswith(expected), result
    assert calls[0]["receipt"]["input_tokens"] == 0
    assert calls[0]["receipt"]["output_tokens"] == 0


@pytest.mark.parametrize("failure", ["unavailable", "timeout"])
async def test_inference_failure_preserves_cause_and_never_retries(tmp_path, failure):
    paths = await asyncio.to_thread(prepare_report_task, tmp_path)
    payload = json.loads(await asyncio.to_thread(paths[1].read_bytes))
    payload["requested_model_profiles"][0]["timeout_ms"] = 1000
    await asyncio.to_thread(paths[1].write_text, json.dumps(payload), encoding="utf-8")
    normal = responder()

    async def respond(request):
        if "/api/chat " in request[0]:
            if failure == "timeout":
                await asyncio.sleep(1.5)
            return 503, {"error": "controlled unavailable inference"}
        return await normal(request)

    async with observed_http_server(respond, allow_disconnect=True) as (endpoint, requests):
        code, result = await invoke(tmp_path, endpoint, paths)
    assert code == 1 and not result["ok"]
    assert sum("/api/chat " in first for first, _ in requests) == 1
    expected = "E_AGENT_MODEL_PROVIDER_" + ("TIMEOUT" if failure == "timeout" else "UNAVAILABLE")
    assert expected in json.dumps(result), result
    assert "E_LOGGING_PREPARATION_REQUIRED" not in json.dumps(result)


async def test_even_well_formed_report_is_refused_when_provider_reports_truncation(tmp_path):
    paths = await asyncio.to_thread(prepare_report_task, tmp_path)
    async with observed_http_server(responder(finish_reason="length")) as (endpoint, requests):
        code, result = await invoke(tmp_path, endpoint, paths)
    assert code == 1 and not result["ok"]
    call = result["iterations"][0]["model_calls"][0]
    assert call["normalized_reason"] == "model_response_truncated"
    assert call["receipt"]["truncated"] is True and call["receipt"]["status"] == "failed"
    assert sum("/api/chat " in first for first, _ in requests) == 1
