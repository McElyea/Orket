"""Integration: native Gardener adapter, CLI, SDK child, SQLite and controlled HTTP."""
import asyncio
import json
import subprocess
import sys

import pytest

from tests.integration.test_gardener_harness_example import commit, invoke, report_response, setup
from tests.integration.test_local_setup_diagnostics import catalog_server as catalog_server

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("size", [67_000, 131_000, 500_000])
def test_large_snapshot_reaches_provider_without_loss(tmp_path, catalog_server, size):
    endpoint, state = catalog_server
    state["response"] = report_response
    paths = setup(tmp_path)
    text = "BEGIN_SNAPSHOT\n" + "x" * min(size, 125000) + "\nEND_SNAPSHOT"
    expected = {"CHECKLIST.md": text}
    (paths[2] / "CHECKLIST.md").write_text(text, encoding="utf-8")
    for index, start in enumerate(range(125000, size, 125000)):
        name = f"extra-{index}.md"
        expected[name] = "x" * min(125000, size - start)
        (paths[2] / name).write_text(expected[name], encoding="utf-8")
    commit(paths[2])
    code, result = invoke(tmp_path, endpoint, paths, extra={
        "ORKET_GARDENER_MAX_FILE_BYTES": "524288", "ORKET_GARDENER_MAX_SNAPSHOT_BYTES": "524288"})
    assert code == 0, result
    inputs = json.loads("".join(row["content"] for row in state["request"]["messages"]
                              if row["role"] == "user"))["inputs"]
    actual = {row["content"].get("path"): row["content"].get("text") for row in inputs
              if isinstance(row["content"], dict)}
    assert all(actual.get(name) == content for name, content in expected.items())
    assert state["calls"].count("/v1/chat/completions") == 1


@pytest.mark.parametrize("defect", ["title_only", "empty_findings", "missing_summary_line"])
def test_content_free_gardener_report_cannot_complete(tmp_path, catalog_server, defect):
    endpoint, state = catalog_server

    def response(request):
        payload = json.loads(report_response(request))
        if defect == "title_only":
            payload["sections"] = {"summary": "Gap checklist for the repository"}
        elif defect == "empty_findings":
            payload["sections"]["findings"] = " "
        else:
            payload["sections"]["summary"] = "Gap checklist for the repository"
        return json.dumps(payload)

    state["response"] = response
    code, envelope = invoke(tmp_path, endpoint, setup(tmp_path))
    assert code == 1 and envelope["is_error"], envelope
    assert envelope["session_id"].startswith("orket:")
    run_id = envelope["session_id"].removeprefix("orket:")
    area = next((tmp_path / "work").glob("run-*"))
    inspected = subprocess.run([sys.executable, "-m", "orket.cli", "agent", "inspect", run_id,
        "--db", str(area / "agent.sqlite3"), "--json"], capture_output=True, text=True, timeout=30, check=True)
    truth = json.loads(inspected.stdout)["final_truth"]
    assert truth["completion_classification"] == "completion_unsatisfied"


@pytest.mark.asyncio
async def test_report_timeout_retains_inspectable_terminal_run(tmp_path):
    from tests.helpers.observed_http_server import observed_http_server
    from tests.integration.test_governed_ollama_reports import responder
    from tests.integration.test_runtime_entrypoints import child

    paths = await asyncio.to_thread(setup, tmp_path)
    normal = responder()
    release = asyncio.Event()

    async def respond(request):
        if "/api/chat " in request[0]:
            await asyncio.wait_for(release.wait(), timeout=50)
        return await normal(request)

    async with observed_http_server(respond, allow_disconnect=True) as (endpoint, requests):
        try:
            code, envelope = await asyncio.to_thread(invoke, tmp_path, endpoint, paths, extra={
                "GARDENER_HARNESS_MODEL": "llama3.2:3b", "ORKET_GARDENER_PROVIDER": "ollama",
                "GARDENER_HARNESS_TIMEOUT": "40"})
        finally:
            release.set()
    assert code == 1 and envelope["blocked"] and envelope["is_error"], envelope
    assert "E_AGENT_MODEL_PROVIDER_TIMEOUT" in envelope["result"]
    run_id = envelope["session_id"].removeprefix("orket:")
    assert run_id in envelope["result"] and "orket agent inspect" in envelope["result"]
    area = next((tmp_path / "work").glob("run-*"))
    for command in ("inspect", "replay"):
        code, output, error = await child(tmp_path, ["-m", "orket.cli", "agent", command, run_id,
            "--db", str(area / "agent.sqlite3"), "--json"])
        assert code == 0, output + error
        result = json.loads(output)
        if command == "replay":
            assert result["status"] == "matched", result
        else:
            assert result["run"]["lifecycle_state"] == "failed_terminal"
            assert result["attempts"][0]["end_timestamp"]
            assert result["attempts"][0]["failure_class"] == "E_AGENT_MODEL_PROVIDER_TIMEOUT"
            assert result["final_truth"]["completion_classification"] == "completion_unsatisfied"
            assert result["iterations"][0]["model_calls"][0]["normalized_reason"] == "E_AGENT_MODEL_PROVIDER_TIMEOUT"
    assert sum("/api/chat " in first for first, _ in requests) == 1


def test_oversized_individual_input_refuses_before_provider(tmp_path, catalog_server):
    endpoint, state = catalog_server
    paths = setup(tmp_path)
    (paths[2] / "CHECKLIST.md").write_text("x" * 270000, encoding="utf-8")
    commit(paths[2])
    code, result = invoke(tmp_path, endpoint, paths, extra={
        "ORKET_GARDENER_MAX_FILE_BYTES": "524288", "ORKET_GARDENER_MAX_SNAPSHOT_BYTES": "524288"})
    assert code == 1 and "E_GARDENER_INPUT_TOO_LARGE" in result["result"]
    assert not state["calls"]


@pytest.mark.asyncio
async def test_native_child_budget_failure_retains_private_protocol_code(tmp_path):
    from orket.extensions.governed_agent_invoker import GovernedAgentSubprocessInvoker
    from orket_extension_sdk.agent_fixtures import prefixed_digest
    from tests.runtime.governed_agent_test_support import TEMPLATE_ROOT, UnexpectedBroker, agent_request, binding_for

    request = agent_request()
    budget = request["remaining_iteration_budget"]
    budget["output_bytes"] = 512
    budget.pop("snapshot_digest")
    budget["snapshot_digest"] = prefixed_digest(budget)
    invoker = GovernedAgentSubprocessInvoker(extension_root=TEMPLATE_ROOT,
        entrypoint="governed_agent:GovernedTicketAgent", allowed_stdlib_modules=("json",), broker=UnexpectedBroker())
    outcome = await invoker.invoke_once(binding=binding_for(request), request_payload=request)
    assert outcome.child_confirmed_stopped
    assert outcome.normalized_reason == "E_SDK_AGENT_AGGREGATE_OUTPUT_EXCEEDED", invoker.last_diagnostic_tail


