"""Public CLI, real agent children and SQLite with explicitly controlled model HTTP."""
import asyncio
import json
import socket
import threading
from datetime import UTC, datetime

import pytest

from orket.adapters.storage import local_agent_example_store
from orket.application.services import local_agent_example_service
from orket.application.services.governed_agent_fixture import _fixture_role_response
from tests.integration.test_local_setup_diagnostics import catalog_server as catalog_server
from tests.integration.test_local_setup_diagnostics import setup
from tests.integration.test_runtime_entrypoints import child

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def controlled_response(payload):
    messages = payload["messages"]
    source = json.loads(messages[-1]["content"])
    role = "planner" if isinstance(source, list) else "critic" if "Review the supplied report" in messages[0]["content"] else "actor"
    return json.dumps(_fixture_role_response(role, source))


async def test_prepared_example_runs_real_children_and_reopens_retained_state(tmp_path, catalog_server):
    endpoint, state = catalog_server
    state["response"] = controlled_response
    project, code, output, error = await setup(tmp_path, endpoint, extra=("--skip-check",))
    assert code == 0, output + error
    args = ["-m", "orket.cli", "demo", "local-agent", "--project", str(project), "--json"]
    code, output, error = await child(tmp_path, args)
    assert code == 0, output + error
    payload = json.loads(output)
    assert payload["ok"] and payload["run"]["lifecycle_state"] == "completed"
    assert [item["disposition"] for item in payload["decisions"]] == ["continue", "complete"]
    assert len([call for call in state["calls"] if call == "/v1/chat/completions"]) == 6
    area = project / ".orket/examples/local-agent"
    report = json.loads(await asyncio.to_thread((area / "report.json").read_bytes))
    assert report == payload and report["model_targets"]["planner"]["requested_provider"] == "llama_cpp"
    for command in ("inspect", "replay"):
        code, output, error = await child(tmp_path, ["-m", "orket.cli", "agent", command, "run-1",
            "--db", str(area / "agent.sqlite3"), "--json"])
        assert code == 0, output + error
        observed = json.loads(output)
        assert observed["ok"]
        if command == "replay":
            assert observed["status"] == "matched"
    before = await asyncio.to_thread((area / "agent.sqlite3").read_bytes)
    code, output, error = await child(tmp_path, args)
    assert code == 1 and not json.loads(output)["ok"], output + error
    assert await asyncio.to_thread((area / "agent.sqlite3").read_bytes) == before
    assert len([call for call in state["calls"] if call == "/v1/chat/completions"]) == 6


async def test_example_cannot_turn_wrong_model_output_into_verified_success(tmp_path, catalog_server):
    endpoint, state = catalog_server

    def wrong(payload):
        value = json.loads(controlled_response(payload))
        value["counts"] = {"open": 999}
        return json.dumps(value)

    state["response"] = wrong
    project, code, output, error = await setup(tmp_path, endpoint, extra=("--skip-check",))
    assert code == 0, output + error
    code, output, error = await child(tmp_path, ["-m", "orket.cli", "demo", "local-agent",
                                               "--project", str(project), "--json"])
    assert code == 1, output + error
    result = json.loads(output)
    assert not result["ok"] and result["observed_result"] == "failure"
    assert "/v1/chat/completions" in state["calls"]


async def test_example_missing_provider_refuses_before_allocating_run(tmp_path):
    with socket.socket() as unlistened:
        unlistened.bind(("127.0.0.1", 0))
        endpoint = f"http://127.0.0.1:{unlistened.getsockname()[1]}/v1"
        project, code, output, error = await setup(tmp_path, endpoint, extra=("--skip-check",))
        assert code == 0, output + error
        code, output, error = await child(tmp_path, ["-m", "orket.cli", "demo", "local-agent",
                                                   "--project", str(project), "--json"])
    assert code == 1 and not json.loads(output)["ok"], output + error
    assert not await asyncio.to_thread((project / ".orket/examples/local-agent").exists)


async def test_example_input_publication_settles_through_repeated_interruption(tmp_path, catalog_server, monkeypatch):
    endpoint, _ = catalog_server
    project, code, output, error = await setup(tmp_path, endpoint, extra=("--skip-check",))
    assert code == 0, output + error
    from dotenv import dotenv_values
    environment = await asyncio.to_thread(dotenv_values, project / ".env")
    entered, release = threading.Event(), threading.Event()
    original = local_agent_example_service.publish_example_inputs

    def held(*args):
        entered.set()
        assert release.wait(10)
        return original(*args)

    monkeypatch.setattr(local_agent_example_service, "publish_example_inputs", held)
    area = project / "held example"
    task = asyncio.create_task(local_agent_example_service.run_local_agent_example(
        project, target=area, now=datetime.now(UTC), environment=environment))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        environment["ORKET_LLM_PROVIDER"] = "ollama"
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        assert not task.done()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 3)
        assert isinstance(result, asyncio.CancelledError)
        request = json.loads(await asyncio.to_thread((area / "request.json").read_bytes))
        assert request["objective_ref"] == "objective:ticket-report"
        assert not await asyncio.to_thread((area / "agent.sqlite3").exists)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 3)


async def test_example_storage_refuses_event_loop_calls_and_outside_project(tmp_path):
    with pytest.raises(RuntimeError, match="E_LOCAL_EXAMPLE_REQUIRES_NATIVE_OWNER"):
        local_agent_example_store.allocate_example(tmp_path, tmp_path / "direct")
    with pytest.raises(ValueError, match="E_LOCAL_EXAMPLE_PATH_OUTSIDE_PROJECT"):
        await asyncio.to_thread(local_agent_example_store.allocate_example, tmp_path, tmp_path.parent / "outside")
    assert not await asyncio.to_thread((tmp_path / "direct").exists)
