"""Layer: integration. A cancelled turn retains its native owner until result-file I/O settles."""
import asyncio

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from tests.helpers.tool_result_persistence import enter, held_worker
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_turn_execution_ownership import ObservedToolbox, executor
from tests.integration.test_turn_executor_control_plane import _context, _issue, _Model, _role

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]


@pytest.mark.parametrize("protocol", [False, True], ids=["ordinary", "protocol"])
@pytest.mark.parametrize("stage", ["operation", "secondary"])
async def test_cancelled_turn_holds_native_owner_through_result_file_worker(tmp_path, protocol, stage):
    db = tmp_path / "control-plane.sqlite3"
    first, second = executor(tmp_path, db), executor(tmp_path, db)
    tools = ObservedToolbox(tmp_path, "first")
    contender_tools, contender_model = ObservedToolbox(tmp_path, "contender"), _Model()
    callback = ("persist_operation_result" if stage == "operation" else
                "append_protocol_receipt" if protocol else "persist_tool_result")
    async with held_worker(first.tool_dispatcher, callback) as (entered, release, finished):
        task = asyncio.create_task(first.execute_turn(_issue(), _role(), _Model(), tools,
                                   _context(protocol_governed_enabled=protocol)))
        try:
            await enter(entered)
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(0.01)
            escaped = task.done()
            contender = await asyncio.wait_for(second.execute_turn(_issue(), _role(), contender_model,
                contender_tools, _context(protocol_governed_enabled=protocol, resume_mode=True)), timeout=5)
            assert not finished.is_set()
        finally:
            release.set()
            outcome, = await asyncio.gather(task, return_exceptions=True)
    assert not escaped and finished.is_set() and isinstance(outcome, asyncio.CancelledError)
    assert not contender.success and "owner_busy" in contender.error
    assert contender_tools.calls == contender_model.calls == 0
    assert tools.calls == 1
    files = AsyncFileTools(tmp_path)
    assert await files.read_file("agent_output/out.txt") == "ok"
    assert await files.read_file("observations/first.txt") == "write completed"
    assert not await asyncio.to_thread((tmp_path / "observations/contender.txt").exists)
    later = await second.execute_turn(_issue(), _role(), contender_model, contender_tools,
                                     _context(protocol_governed_enabled=protocol, resume_mode=True))
    assert not later.success and "dispatch outcome unknown" in later.error
    assert contender_tools.calls == contender_model.calls == 0
    service = first.tool_dispatcher.control_plane_service
    run = await service.execution_repository.get_run_record(run_id="turn-tool-run:run-1:ISSUE-1:developer:0001")
    steps = await service.execution_repository.list_step_records(attempt_id=run.current_attempt_id)
    effects = await service.publication.repository.list_effect_journal_entries(run_id=run.run_id)
    assert len(steps) == 1 and steps[0].output_ref is None and not effects
    assert run.final_truth_record_id is None
