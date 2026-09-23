"""A cooperating second caller cannot run a turn while its first owner executes."""
from __future__ import annotations

import asyncio
import sys

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_resource_lifecycle import lease_id_for_run
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain import LeaseStatus, RunState
from orket.core.domain.state_machine import StateMachine
from tests.helpers.turn_artifacts import artifact_test_utc_now
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_turn_executor_control_plane import _context, _issue, _Model, _role, _Toolbox

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]


class ObservedToolbox(_Toolbox):
    def __init__(self, workspace, name, entered=None, release=None):
        super().__init__()
        self.files, self.name, self.entered, self.release = AsyncFileTools(workspace), name, entered, release

    async def execute(self, tool_name, args, context=None):
        if self.entered is not None:
            self.entered.set()
            await self.release.wait()
        result = await super().execute(tool_name, args, context)
        await self.files.write_file(args["path"], args["content"])
        await self.files.write_file(f"observations/{self.name}.txt", "write completed")
        return result


def executor(workspace, db):
    return TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=workspace), workspace=workspace,
                        control_plane_service=build_turn_tool_control_plane_service(db), utc_now=artifact_test_utc_now)


@pytest.mark.parametrize("protocol", [False, True], ids=["ordinary", "protocol"])
@pytest.mark.parametrize("resume", [False, True], ids=["reentry", "resume"])
# Layer: integration
async def test_active_turn_excludes_competing_dispatch_before_model_or_effect(tmp_path, protocol, resume):
    db = tmp_path / "control_plane.sqlite3"
    first, second = executor(tmp_path, db), executor(tmp_path, db)
    entered, release = asyncio.Event(), asyncio.Event()
    first_tools = ObservedToolbox(tmp_path, "first", entered, release)
    second_tools, second_model = ObservedToolbox(tmp_path, "second"), _Model()
    task = asyncio.create_task(first.execute_turn(_issue(), _role(), _Model(), first_tools,
                                                 _context(protocol_governed_enabled=protocol)))
    try:
        await asyncio.wait_for(entered.wait(), timeout=20)
        other = await asyncio.wait_for(second.execute_turn(_issue(), _role(), second_model, second_tools,
            _context(protocol_governed_enabled=protocol, resume_mode=resume)), timeout=20)
    finally:
        release.set()
        completed = await asyncio.wait_for(task, timeout=20)
    assert second_tools.calls == 0 and second_model.calls == 0
    assert not other.success and completed.success
    assert first_tools.calls == 1 and await AsyncFileTools(tmp_path).read_file("observations/first.txt") == "write completed"
    assert not await asyncio.to_thread((tmp_path / "observations/second.txt").exists)


# Layer: integration
async def test_completed_turn_reentry_remains_observation_only(tmp_path):
    db = tmp_path / "control_plane.sqlite3"
    tools = ObservedToolbox(tmp_path, "first")
    first = await executor(tmp_path, db).execute_turn(_issue(), _role(), _Model(), tools, _context())
    later_tools, later_model = ObservedToolbox(tmp_path, "second"), _Model()
    later = await executor(tmp_path, db).execute_turn(_issue(), _role(), later_model, later_tools, _context())
    assert first.success and later.success and tools.calls == 1
    assert later_model.calls == later_tools.calls == 0


class InterruptedToolbox(ObservedToolbox):
    def __init__(self, workspace, interruption):
        super().__init__(workspace, "first")
        self.interruption = interruption

    async def execute(self, tool_name, args, context=None):
        await super().execute(tool_name, args, context)
        raise self.interruption("dispatch ended without a result receipt")


@pytest.mark.parametrize("protocol", [False, True], ids=["ordinary", "protocol"])
@pytest.mark.parametrize("resume", [False, True], ids=["reentry", "resume"])
@pytest.mark.parametrize("interruption", [RuntimeError, asyncio.CancelledError], ids=["error", "cancel"])
# Layer: integration
async def test_interrupted_dispatch_retains_uncertainty_and_refuses_reexecution(tmp_path, protocol, resume, interruption):
    db = tmp_path / "control_plane.sqlite3"
    first = executor(tmp_path, db)
    tools = InterruptedToolbox(tmp_path, interruption)
    execution = first.execute_turn(_issue(), _role(), _Model(), tools, _context(protocol_governed_enabled=protocol))
    if interruption is asyncio.CancelledError:
        with pytest.raises(asyncio.CancelledError):
            await execution
    else:
        assert not (await execution).success
    later_tools, later_model = ObservedToolbox(tmp_path, "second"), _Model()
    later = await executor(tmp_path, db).execute_turn(_issue(), _role(), later_model, later_tools,
        _context(protocol_governed_enabled=protocol, resume_mode=resume))
    assert not later.success and "dispatch outcome unknown" in later.error
    assert tools.calls == 1 and later_tools.calls == later_model.calls == 0
    files = AsyncFileTools(tmp_path)
    assert await files.read_file("observations/first.txt") == "write completed"
    assert not await asyncio.to_thread((tmp_path / "observations/second.txt").exists)
    service = first.tool_dispatcher.control_plane_service
    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    run = await service.execution_repository.get_run_record(run_id=run_id)
    assert run.lifecycle_state is RunState.EXECUTING and run.final_truth_record_id is None
    steps = await service.execution_repository.list_step_records(attempt_id=run.current_attempt_id)
    assert len(steps) == 1 and steps[0].closure_classification == "dispatch_started"
    assert steps[0].output_ref is None and steps[0].capability_used is None and not steps[0].resources_touched
    assert not await service.publication.repository.list_effect_journal_entries(run_id=run_id)
    lease = await service.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
    assert lease.status is LeaseStatus.ACTIVE


@pytest.mark.parametrize("protocol", [False, True], ids=["ordinary", "protocol"])
# Layer: integration
async def test_native_owner_death_does_not_authorize_tool_redispatch(tmp_path, protocol):
    db = tmp_path / "control_plane.sqlite3"
    child = await asyncio.create_subprocess_exec(sys.executable, "-m", "tests.helpers.turn_execution_worker",
        str(tmp_path), str(db), "protocol" if protocol else "ordinary",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    files = AsyncFileTools(tmp_path)
    try:
        async with asyncio.timeout(30):
            while not await asyncio.to_thread((tmp_path / "child-ready.txt").exists):
                if child.returncode is not None:
                    stdout, stderr = await child.communicate()
                    pytest.fail(f"child exited {child.returncode}: {stdout!r} {stderr!r}")
                await asyncio.sleep(0.02)
        contender_tools, contender_model = ObservedToolbox(tmp_path, "second"), _Model()
        busy = await executor(tmp_path, db).execute_turn(_issue(), _role(), contender_model, contender_tools, _context())
        assert not busy.success and "owner_busy" in busy.error
        assert contender_tools.calls == contender_model.calls == 0
    finally:
        if child.returncode is None:
            child.kill()
        stdout, stderr = await asyncio.wait_for(child.communicate(), timeout=15)
        await files.write_file("child.stdout.txt", stdout.decode("utf-8", errors="replace"))
        await files.write_file("child.stderr.txt", stderr.decode("utf-8", errors="replace"))
    assert child.returncode is not None and child.returncode != 0
    later_tools, later_model = ObservedToolbox(tmp_path, "second"), _Model()
    later = await executor(tmp_path, db).execute_turn(_issue(), _role(), later_model, later_tools,
        _context(protocol_governed_enabled=protocol, resume_mode=True))
    assert not later.success and "dispatch outcome unknown" in later.error
    assert later_tools.calls == later_model.calls == 0
    assert await files.read_file("observations/first.txt") == "write completed"
    assert not await asyncio.to_thread((tmp_path / "observations/second.txt").exists)
