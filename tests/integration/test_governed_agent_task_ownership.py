"""Integration: native input settlement and clock/environment capture for task admission."""
import asyncio
import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.application.services import governed_agent_task_service as owner
from orket.application.services.governed_agent_submission_service import GovernedAgentProviderOptions
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from tests.helpers.governed_agent_task import prepare_report_task, report_response
from tests.integration.test_local_setup_diagnostics import catalog_server as catalog_server

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def arguments(root, paths, *, environment, clock, provider=None):
    catalog, submission, inputs = paths
    return dict(project_root=root, db_path=Path("agent.sqlite3"), catalog_path=catalog,
                submission_path=submission, inputs_path=inputs,
                provider=provider or GovernedAgentProviderOptions(deterministic_fixture=True),
                environment=environment, run_id="task-observation", utc_now=clock)


@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_task_owns_native_input_read_until_settled(tmp_path, monkeypatch, mode):
    paths = await asyncio.to_thread(prepare_report_task, tmp_path)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = owner.read_agent_task_json

    def held(path):
        entered.set()
        assert release.wait(10)
        result = original(path)
        finished.set()
        return result

    monkeypatch.setattr(owner, "read_agent_task_json", held)
    kwargs = arguments(tmp_path, paths, environment={}, clock=lambda: datetime.now(UTC))

    async def invoke():
        async with asyncio.timeout(0.1 if mode == "timeout" else 20):
            return await owner.run_governed_agent_task(**kwargs)

    task = asyncio.create_task(invoke())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if mode == "cancel":
            task.cancel()
        await asyncio.sleep(0.15)
        assert not task.done() and not finished.is_set()
        await asyncio.wait_for(asyncio.sleep(0), 0.5)
    finally:
        release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await task
    assert finished.is_set() and not (tmp_path / "agent.sqlite3").exists()


async def test_task_captures_paths_environment_and_observes_time_after_model(tmp_path, monkeypatch, catalog_server):
    endpoint, state = catalog_server
    paths = await asyncio.to_thread(prepare_report_task, tmp_path)
    paths = tuple(path.relative_to(tmp_path) for path in paths)
    environment = {"ORKET_LLM_LLAMA_CPP_BASE_URL": endpoint}
    entered, release = asyncio.Event(), asyncio.Event()
    original = owner.run_owned_thread
    now = datetime.now(UTC)
    times = []

    def clock():
        value = now + timedelta(seconds=1 if "/v1/chat/completions" in state["calls"] else 0)
        times.append(value)
        return value

    async def held(operation, **kwargs):
        entered.set()
        await release.wait()
        return await original(operation, **kwargs)

    monkeypatch.setattr(owner, "run_owned_thread", held)
    state["response"] = lambda _: json.dumps(report_response())
    task = asyncio.create_task(owner.run_governed_agent_task(**arguments(
        tmp_path, paths, environment=environment, clock=clock,
        provider=GovernedAgentProviderOptions(model=DEFAULT_LOCAL_MODEL))))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        environment["ORKET_LLM_LLAMA_CPP_BASE_URL"] = "http://127.0.0.1:1/v1"
        monkeypatch.chdir(tmp_path.parent)
        release.set()
        result = await asyncio.wait_for(task, 30)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert result["ok"] and result["db_path"] == str(tmp_path / "agent.sqlite3")
    assert times == [now, now + timedelta(seconds=1)]
    snapshots = await AsyncGovernedAgentRepository(tmp_path / "agent.sqlite3").list_iteration_snapshots(
        run_id="task-observation")
    request = snapshots[0].request_payload
    assert datetime.fromisoformat(request["deadline_utc"]) == now + timedelta(seconds=120)
    assert request["extension_config"]["governed_submission"]["verifier_class"] == "structured_report.v1"
