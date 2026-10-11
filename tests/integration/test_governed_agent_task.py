"""Integration: real CLI, external SDK child, SQLite and controlled provider HTTP."""
import asyncio
import json

import pytest

from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from orket_extension_sdk import canonical_digest_sha256
from tests.helpers.governed_agent_task import prepare_report_task, report_response
from tests.integration.test_local_setup_diagnostics import catalog_server as catalog_server
from tests.integration.test_runtime_entrypoints import child

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def invoke(root, endpoint, catalog, submission, inputs):
    return await child(root, ["-m", "orket.cli", "agent", "run", "--catalog", str(catalog),
        "--submission", str(submission), "--inputs", str(inputs), "--db", str(root / "agent.sqlite3"),
        "--model", DEFAULT_LOCAL_MODEL, "--provider", "llama_cpp", "--provider-base-url", endpoint, "--json"])


async def test_public_task_accepts_new_objective_and_replays_real_state(tmp_path, catalog_server):
    endpoint, state = catalog_server
    def respond(request):
        shape = request["response_format"]
        assert shape["type"] == "json_schema" and shape["json_schema"]["strict"] is True
        assert shape["json_schema"]["schema"]["properties"]["sections"]["required"] == ["summary"]
        return json.dumps(report_response())
    state["response"] = respond
    paths = await asyncio.to_thread(prepare_report_task, tmp_path)
    code, output, error = await invoke(tmp_path, endpoint, *paths)
    result = json.loads(output)
    assert code == 0, str({key: result.get(key) for key in ("error", "normalized_reason", "decisions")}) + error
    assert result["ok"] and result["run"]["lifecycle_state"] == "completed"
    assert len(result["iterations"]) == 1
    assert json.loads(result["iterations"][0]["advisory_proposal"]) == report_response()
    assert result["decisions"][0]["rule"] == "verified_objective_satisfied"
    assert state["calls"].count("/v1/chat/completions") == 1
    run_id = result["run"]["run_id"]
    assert run_id.startswith("agent-run:")
    for command in ("inspect", "replay"):
        code, output, error = await child(tmp_path, ["-m", "orket.cli", "agent", command, run_id,
            "--db", str(tmp_path / "agent.sqlite3"), "--json"])
        assert code == 0, output + error
        payload = json.loads(output)
        assert payload["ok"]
        if command == "replay":
            assert payload["status"] == "matched"
        else:
            assert payload["final_truth"] == result["final_truth"]
            assert payload["iterations"][0]["advisory_proposal"] == result["iterations"][0]["advisory_proposal"]


@pytest.mark.parametrize("defect", ["missing_section", "foreign_source", "not_advisory", "plain_text",
                                  "duplicate_source", "blank_section"])
async def test_public_task_refuses_invalid_report_without_false_success(tmp_path, catalog_server, defect):
    endpoint, state = catalog_server
    report = report_response()
    if defect == "missing_section":
        report["sections"] = {}
    elif defect == "foreign_source":
        report["source_refs"].append("unseen:secret")
    elif defect == "not_advisory":
        report["advisory"] = False
    elif defect == "duplicate_source":
        report["source_refs"] = [report["source_refs"][0]] * len(report["source_refs"])
    elif defect == "blank_section":
        report["sections"]["summary"] = " "
    state["response"] = lambda _: "done" if defect == "plain_text" else json.dumps(report)
    paths = await asyncio.to_thread(prepare_report_task, tmp_path)
    code, output, error = await invoke(tmp_path, endpoint, *paths)
    assert code == 1, output + error
    result = json.loads(output)
    assert not result["ok"]
    assert result["final_truth"] is None or result["final_truth"]["result_class"] != "success"
    assert state["calls"].count("/v1/chat/completions") == 1
    if defect != "plain_text":
        iteration = result["iterations"][0]
        assert iteration["state"] == "decided"
        call = iteration["model_calls"][0]
        if defect in {"duplicate_source", "blank_section"}:
            # Passing generation/broker schema is insufficient: the independent host verifier must refuse.
            assert json.loads(iteration["advisory_proposal"]) == report
            assert call["receipt"]["status"] == "returned"
        else:
            assert iteration["advisory_proposal"] is None
            assert call["receipt"]["status"] == "failed"
            assert call["normalized_reason"] == "model_response_contract_failed"


@pytest.mark.parametrize("defect", ["verifier", "policy", "extension", "budget", "input_digest"])
async def test_task_admission_refuses_before_provider_and_database(tmp_path, catalog_server, defect):
    endpoint, state = catalog_server
    catalog, submission, inputs = await asyncio.to_thread(prepare_report_task, tmp_path)
    target = inputs if defect == "input_digest" else submission
    payload = json.loads(await asyncio.to_thread(target.read_bytes))
    if defect == "verifier":
        payload["verifier_class"] = "arbitrary.module:AlwaysPass"
    elif defect == "policy":
        payload["allowed_capabilities"].append("write_file")
    elif defect == "extension":
        payload["extension_id"] = "wrong.extension"
    elif defect == "budget":
        payload["run_budget"]["iterations"] = 2
        budget = payload["run_budget"]
        budget["snapshot_digest"] = "sha256:" + canonical_digest_sha256(
            {key: value for key, value in budget.items() if key != "snapshot_digest"})
    else:
        payload[-1]["content"] = "changed without updating digest"
    await asyncio.to_thread(target.write_text, json.dumps(payload), encoding="utf-8")
    code, output, error = await invoke(tmp_path, endpoint, catalog, submission, inputs)
    assert code == 1, output + error
    assert not json.loads(output)["ok"]
    assert not state["calls"]
    assert not (tmp_path / "agent.sqlite3").exists()
