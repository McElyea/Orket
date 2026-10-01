"""Integration: public execution retains native policy validation and SQLite publication."""
import asyncio

import pytest

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.application.services.outward_connector_service import OutwardConnectorPolicyError, OutwardConnectorService
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import bind_logging, prepare_logging
from tests.helpers.application_root_controls import NativeHold
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_authorization import outward_api
from tests.helpers.outward_model_admission import admission_snapshot
from tests.helpers.runtime_verification_hold import sqlite_response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def submit(context, calls):
    return await context.outward_run_service.submit({"run_id": "bt0-run", "task": {
        "description": "Native policy owner proof", "instruction": "Write only after approval",
        "acceptance_contract": {"governed_tool_sequence": calls[:1]}},
        "policy_overrides": {"approval_required_tools": ["write_file"], "max_turns": 1}})


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", ["none", "policy", "native"])
async def test_public_execution_retains_policy_worker(tmp_path, monkeypatch, boundary, stop, failure, record_property):
    db, inputs, calls = boundary
    hold, seen = NativeHold(), []
    native = OutwardConnectorService.validate_policy
    error = OSError("controlled native policy worker failure")

    def held(service, tool, args):
        if hold.entered.is_set():
            return native(service, tool, args)
        hold.wait()
        try:
            seen.append(service.executor.file_tools.async_fs.workspace_root)
            native(service, tool, args)
            if failure == "policy":
                raise OutwardConnectorPolicyError(tool, "controlled policy refusal")
            if failure == "native":
                raise error
        finally:
            hold.finished.set()

    async with outward_api(tmp_path, inputs) as (_client, context):
        await submit(context, calls)
        execution = context.outward_run_execution_service
        monkeypatch.setattr(OutwardConnectorService, "validate_policy", held)
        deadline = asyncio.timeout(None)

        async def dispatch():
            async with asyncio.timeout(10), deadline:
                return await execution.start_if_ready("bt0-run")

        with bind_logging(await prepare_logging(LoggingInputs(tmp_path, timezone_name="UTC"))):
            task = asyncio.create_task(dispatch())
            try:
                assert await asyncio.to_thread(hold.entered.wait, 5)
                execution.connector_service.executor.file_tools.async_fs.workspace_root = tmp_path / "late-root"
                monkeypatch.chdir(tmp_path)
                assert await sqlite_response(tmp_path / "observer.sqlite", record_property) < 0.5
                if stop == "cancel":
                    task.cancel("first")
                    await asyncio.sleep(0)
                    task.cancel("repeated")
                if stop == "timeout":
                    deadline.reschedule(asyncio.get_running_loop().time() + 0.1)
                await asyncio.sleep(0.15 if stop == "timeout" else 0.04)
                assert not task.done(), "transaction returned while policy native work remained active"
                hold.release.set()
                result, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
                assert hold.finished.is_set() and not hold.expired and seen == [tmp_path]
                await check_published_state(db, tmp_path, result, stop, failure, error)
            finally:
                hold.release.set()
                await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def check_published_state(db, root, result, stop, failure, error):
    admission = await admission_snapshot(db)
    proposals = await OutwardApprovalStore(db).list(run_id="bt0-run")
    events = await OutwardRunEventStore(db).list_for_run("bt0-run")
    if failure == "native":
        assert result is error
    elif failure == "policy":
        assert result.status == "completed" and result.stop_reason == "controlled policy refusal"
        assert any(event.event_type == "run_completed" and event.payload["outcome"] == "policy_rejected" for event in events)
    elif stop != "none":
        assert isinstance(result, asyncio.CancelledError if stop == "cancel" else TimeoutError)
    else:
        assert result.status == "approval_required" and len(proposals) == 1
    complete = failure == "policy" or (failure == "none" and stop == "none")
    assert admission.state == ("published" if complete else "observed")
    assert len(proposals) == int(failure == "none" and stop == "none")
    if not complete:
        assert {event.event_type for event in events} == {"run_submitted", "run_started", "turn_started"}
    assert not await asyncio.to_thread((root / "first.txt").exists)
    assert not await asyncio.to_thread((root / "late-root/first.txt").exists)
