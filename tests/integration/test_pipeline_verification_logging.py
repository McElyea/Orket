"""Real pipeline verification binds its logging selection in the operation task."""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import nullcontext

import pytest

from orket.adapters.observability.logging_context import selected_logging
from orket.application.services.command_process_supervisor import CommandProcessCancelled
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.exceptions import CardNotFound
from orket.logging import bind_logging, prepare_logging, settle_log_write_frontier
from orket.runtime.execution.execution_pipeline import ExecutionPipeline

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _verify_and_check_context(pipeline, issue_id):
    before = selected_logging(required=False)
    try:
        return await pipeline.verify_issue(issue_id)
    finally:
        assert selected_logging(required=False) is before


async def _await_fixture_start(task, marker):
    for _ in range(500):
        if await asyncio.to_thread(marker.exists):
            return
        if task.done():
            await task
            pytest.fail("Verification finished without starting the fixture")
        await asyncio.sleep(0.01)
    pytest.fail("Verification fixture did not start")


@pytest.mark.parametrize("outer_binding", [False, True], ids=["unbound", "other-caller"])
@pytest.mark.parametrize("outcome", ["success", "cancel", "missing"])
async def test_pipeline_verification_owns_logging_and_restores_caller(
    test_root, workspace, db_path, outer_binding, outcome, record_property,
):
    environment = {**os.environ, "ORKET_DISABLE_SANDBOX": "1", "ORKET_TIMEZONE": "UTC",
                   "ORKET_DURABLE_ROOT": str(test_root / "durable"),
                   "ORKET_VERIFY_EXECUTION_MODE": "subprocess", "ORKET_VERIFY_TIMEOUT_SEC": "15"}
    inputs = RuntimeConstructionInputs(test_root, environment, "{}", "{}")
    caller = await prepare_logging(LoggingInputs(test_root / "caller", timezone_name="America/Phoenix"))
    source = ("from pathlib import Path\nimport time\ndef verify(data):\n"
              "    Path(data['marker']).touch()\n"
              f"    time.sleep({30 if outcome == 'cancel' else 0})\n    return 1\n")
    await asyncio.to_thread((workspace / "verification/fixture.py").write_text, source, encoding="utf-8")
    marker = workspace / "fixture-started"
    async with ExecutionPipeline.open(
        workspace, config_root=test_root, db_path=db_path, construction_inputs=inputs,
    ) as pipeline:
        await pipeline.async_cards.save({"id": "LOGGING", "summary": "Logging selection", "seat": "developer",
            "verification": {"fixture_path": "verification/fixture.py", "scenarios": [{"id": "one",
                "description": "native fixture", "input_data": {"marker": str(marker)}, "expected_output": 1}]}})
        with bind_logging(caller) if outer_binding else nullcontext():
            before = selected_logging(required=False)
            task = asyncio.create_task(_verify_and_check_context(pipeline, "absent" if outcome == "missing" else "LOGGING"))
            try:
                if outcome == "missing":
                    with pytest.raises(CardNotFound):
                        await task
                elif outcome == "cancel":
                    await _await_fixture_start(task, marker)
                    task.cancel()
                    with pytest.raises(CommandProcessCancelled) as caught:
                        await asyncio.wait_for(task, 7)
                    assert caught.value.lifetime.cleanup_confirmed
                else:
                    result = await task
                    retained = (await pipeline.async_cards.get_by_id("LOGGING")).verification
                    assert result.passed == 1 and result.process_lifetime["cleanup_confirmed"]
                    assert retained["last_run"]["passed"] == 1 and await asyncio.to_thread(marker.exists)
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            assert selected_logging(required=False) is before
    assert pipeline._closed
    await asyncio.to_thread(settle_log_write_frontier)
    log_path = workspace / "orket.log"
    text = await asyncio.to_thread(log_path.read_text, encoding="utf-8") if await asyncio.to_thread(log_path.exists) else ""
    rows = [json.loads(line) for line in text.splitlines()]
    events = [row for row in rows if row["event"] == "verification_started"]
    assert len(events) == (0 if outcome == "missing" else 1)
    assert all(row["timestamp"].endswith("+00:00") for row in events)
    record_property("pipeline_verification_logging", json.dumps({"outcome": outcome,
        "outer_binding": outer_binding, "events": events, "closed": pipeline._closed}))
