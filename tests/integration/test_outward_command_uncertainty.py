"""Layer: integration. Lost supervisor acknowledgement cannot admit effect replay."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from orket.adapters.execution.owned_command_process import WORKER as SUPERVISOR
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from tests.helpers.outward_authorization import append_command, approve, effect_snapshot, outward_api, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary
from tests.integration.test_verification_process_lifetime import (
    WORKER,
    assert_stopped,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def supervisor_of(process):
    # Only a fixture ancestor executing the exact package-owned worker is eligible.
    for parent in process.parents():
        if any(Path(arg).name == SUPERVISOR.name and Path(arg).resolve() == SUPERVISOR.resolve()
               for arg in parent.cmdline()[1:]):
            return parent
    raise AssertionError("Package-owned supervisor missing from fixture ancestry")


@pytest.mark.parametrize("stop", ["cancel", "kill-supervisor"])
# Layer: integration
async def test_unfinished_command_retains_dispatch_intent_across_api_reentry(tmp_path, boundary, monkeypatch, caplog, stop):
    db_path, inputs, _ = boundary
    calls = append_command(monkeypatch)
    calls[0]["args"]["command"] = [sys.executable, str(WORKER), str(tmp_path), "2", "detached", "ignore-term"]
    processes, task = [], None
    try:
        async with outward_api(tmp_path, inputs) as (client, _context):
            proposal = await submit_sequence(client, calls)
            task = asyncio.create_task(approve(client, proposal))
            processes = await await_tree(tmp_path)
            if stop == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 6)
                await assert_stopped(processes, tmp_path)
            else:
                supervisor = await asyncio.to_thread(supervisor_of, processes[-1])
                await asyncio.to_thread(supervisor.kill)
                await asyncio.to_thread(supervisor.wait, timeout=5)
                response = await asyncio.wait_for(task, 10)
                assert response.status_code == 409 and response.json()["detail"] == "E_COMMAND_EXECUTION_UNCERTAIN"
            event, = [row.orket_record["data"] for row in caplog.records
                      if row.message == "outward_connector_interrupted"]
            assert event["process_lifetime"]["cleanup_confirmed"] is (stop == "cancel")
            assert event["observation"] == ("cancelled" if stop == "cancel" else "unresolved")
            before, journal = await effect_snapshot(db_path, proposal)
            assert before.state == "dispatching" and before.receipt_digest is None
        async with outward_api(tmp_path, inputs) as (client, _context):
            response = await approve(client, proposal)
            assert response.status_code == 409 and response.json()["detail"] == "E_OUTWARD_EFFECT_IN_FLIGHT_OR_UNCERTAIN"
        after, after_journal = await effect_snapshot(db_path, proposal)
        assert after == before and after_journal == journal
        events = await OutwardRunEventStore(db_path).list_for_run("bt0-run")
        assert not any(event.event_type == "tool_invoked" for event in events)
    finally:
        if not processes:
            processes = await asyncio.to_thread(observe_processes, tmp_path)
        await asyncio.to_thread(stop_observed, processes)
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
