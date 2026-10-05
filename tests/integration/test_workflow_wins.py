"""Layer: integration. Native fixtures and supervised API failure ownership."""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks.job_outcomes import observe_job
from benchmarks.phase5_load_test import LoadResult
from orket.application.services.application_runtime_lifetime import ApplicationRuntimeLifetime
from orket.interfaces.api_invocation import schedule_api_invocation_task
from orket.state import GlobalState
from scripts.benchmarks.isolated_project import prepare_project
from scripts.benchmarks.task_acceptance import FUNCTION_VERIFIER, declare_task_acceptance
from scripts.governance.check_workflow_preflight import inspect_workflow

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def test_isolated_projects_preserve_caller_board_and_retained_assets(tmp_path):
    source = tmp_path / "source"
    board = source / "model/core/rocks/run_the_business.json"
    board.parent.mkdir(parents=True)
    board.write_bytes(b'{"epics":[{"epic":"operator"}]}')
    for name in ("one", "two"):
        project = prepare_project(source, tmp_path / name, "core")
        assert json.loads((project / "model/core/rocks/run_the_business.json").read_text())["epics"] == []
    assert board.read_bytes() == b'{"epics":[{"epic":"operator"}]}'
    with pytest.raises(FileExistsError):
        prepare_project(source, tmp_path / "one", "core")


def test_stored_preflight_detects_missing_acceptance_before_inference():
    assert inspect_workflow(ROOT, "standard")["ready"]
    assert inspect_workflow(ROOT, "qa_completion_test")["ready"]
    report = inspect_workflow(ROOT, "challenge_workflow_runtime")
    assert not report["ready"] and any("missing completion_acceptance" in error for error in report["errors"])


def test_function_acceptance_executes_real_program_and_refuses_metadata_only(tmp_path):
    task = {"id": "1", "evaluation": {"type": "function_examples", "function_name": "double",
                                     "examples": [{"args": [3], "expected": 6}]}}
    epic = {"issues": [{"note": "Implement double"}]}
    declare_task_acceptance(epic, task, tmp_path)
    definition = epic["issues"][0]["params"]["completion_acceptance"]
    program = tmp_path / "agent_output/main.py"
    program.write_text("def double(n):\n    return n * 2\n")
    command = [sys.executable, str(tmp_path / definition["entrypoint"]), *definition["cases"][0]["arguments"]]
    assert json.loads(subprocess.check_output(command, text=True)) == 6
    program.write_text("def double(n):\n    return 0\n")
    assert json.loads(subprocess.check_output(command, text=True)) != 6
    assert (tmp_path / definition["entrypoint"]).read_text() == FUNCTION_VERIFIER
    with pytest.raises(ValueError, match="explicit function_examples"):
        declare_task_acceptance(epic, {"id": "1"}, tmp_path)


@pytest.mark.asyncio
async def test_api_background_native_error_retained_and_task_removed(tmp_path, caplog):
    class Owner(ApplicationRuntimeLifetime):
        async def _close_final_resource(self):
            self.final_resource_closed = True
    class Target:
        async def run(self):
            await asyncio.to_thread((tmp_path / "missing.txt").read_bytes)
    owner = Owner()
    owner.runtime_state = GlobalState()
    await schedule_api_invocation_task(Target(), {"method_name": "run"}, "run", "failed-job", runtime_getter=lambda: owner)
    task = await owner.runtime_state.get_task("failed-job")
    await task
    assert not owner.accepting_work
    assert await owner.runtime_state.get_tasks("failed-job") == []
    with pytest.raises(RuntimeError, match="teardown failed") as observed:
        await owner.close()
    assert isinstance(observed.value.__cause__, FileNotFoundError)
    assert "Application background task failed" in caplog.text


@pytest.mark.asyncio
async def test_prestart_cancellation_unregisters_at_owned_teardown(tmp_path):
    class Owner(ApplicationRuntimeLifetime):
        async def _close_final_resource(self):
            self.final_resource_closed = True
    class Target:
        async def run(self):
            raise AssertionError("Canceled before invocation")
    owner = Owner()
    owner.runtime_state = GlobalState()
    await schedule_api_invocation_task(Target(), {"method_name": "run"}, "run", "canceled-job", runtime_getter=lambda: owner)
    task = await owner.runtime_state.get_task("canceled-job")
    task.cancel()
    await owner.close()
    assert owner.closed and await owner.runtime_state.get_tasks("canceled-job") == []


def test_load_error_rate_counts_each_request_once():
    assert LoadResult([1, 2, 3, 4], 2).as_dict()["error_rate_percent"] == 50


@pytest.mark.asyncio
async def test_http_admission_is_not_job_completion():
    import httpx
    # Controlled HTTP protocol cases, not proof of a real API/model run.
    def respond(request):
        if request.method == "POST":
            return httpx.Response(200, json={"session_id": "unaccepted"})
        return httpx.Response(200, json={"raw_status": "completed", "completion_accepted": False})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        row = await observe_job(client, "http://test", {}, asset_id="demo", expected_missing=False, deadline_seconds=1)
    assert row["outcome"] == "terminal_unaccepted" and not row["completion_accepted"]


def test_missing_target_is_rejected_without_background_work(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from orket.interfaces.api import create_api_app
    monkeypatch.setenv("ORKET_API_KEY", "local-test-key")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    with TestClient(create_api_app(project_root=tmp_path)) as client:
        headers = {"X-API-Key": "local-test-key"}
        result = client.post("/v1/system/run-active", json={"issue_id": "missing-card"}, headers=headers)
        assert result.status_code == 404
        assert client.get("/v1/system/heartbeat", headers=headers).json()["active_tasks"] == 0


@pytest.mark.asyncio
async def test_native_stream_read_timeout_preserves_error_type():
    from orket.application.services.model_stream_http_service import ModelStreamHttpService
    from orket.streaming.model_provider import OpenAICompatModelStreamProvider, ProviderEventType, ProviderTurnRequest
    from tests.helpers.observed_http_server import observed_http_server
    async def never_respond(request):
        assert request[0].startswith("POST ")
        return None
    async with observed_http_server(never_respond) as (address, requests):
        provider = OpenAICompatModelStreamProvider(model_id="controlled-http", base_url=address, timeout_s=1,
            http_client_owner=ModelStreamHttpService(backend="openai_compat", base_url=address, timeout_s=1))
        events = [event async for event in provider.start_turn(ProviderTurnRequest(input_config={"max_tokens": 1}))]
    errors = [event.payload for event in events if event.event_type is ProviderEventType.ERROR]
    assert len(requests) == 1 and errors == [{"error": "ReadTimeout", "error_type": "ReadTimeout"}]
