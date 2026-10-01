"""Integration: structural adoption retains required events and preceding real file effects."""
import asyncio
import json
from copy import deepcopy

import pytest

from orket.application.services import structural_reconciliation_service as reconciliation
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import bind_logging, prepare_logging
from tests.helpers.application_root_controls import NativeHold, contents, prepare_trees
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.integration.test_bug_fix_event_inputs import records

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
TARGET = "reconciler_orphan_epic_adopted"


def install(monkeypatch, owner, hold, state, failure):
    native, event = reconciliation.log_event, owner._event

    async def observed(name, payload, workspace):
        if name == TARGET:
            state["payload"], state["expected"] = payload, deepcopy(payload)
        return await event(name, payload, workspace)

    def held(name, payload, *, workspace):
        if name != TARGET:
            return native(name, payload, workspace=workspace)
        hold.wait()
        try:
            if failure == "before":
                raise state["failure"]
            native(name, payload, workspace=workspace)
            if failure == "after":
                raise state["failure"]
        finally:
            hold.finished.set()

    monkeypatch.setattr(owner, "_event", observed)
    monkeypatch.setattr(reconciliation, "log_event", held)


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", ["none", "before", "after"])
async def test_reconciliation_required_event_matches_committed_adoption(tmp_path, monkeypatch, stop, failure, record_property):
    first, other = await asyncio.to_thread(prepare_trees, tmp_path)
    original_other = await asyncio.to_thread(contents, other)
    owner = reconciliation.StructuralReconciler(first / "model", first / "workspace/default")
    hold, state = NativeHold(), {"failure": OSError("controlled reconciliation event failure")}
    install(monkeypatch, owner, hold, state, failure)

    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await owner.reconcile()

    with bind_logging(await prepare_logging(LoggingInputs(first, timezone_name="MST"))):
        task = asyncio.create_task(dispatch())
        try:
            assert await asyncio.to_thread(hold.entered.wait, 3)
            assert await sqlite_response(tmp_path / "observer.sqlite", record_property) < 0.5
            current = await asyncio.to_thread(contents, first)
            assert json.loads(current["core/rocks/run_the_business.json"])["epics"] == [{"epic": "product_plan", "department": "product"}]
            state["payload"]["department"] = "late mutation"
            owner.workspace, owner.root_path = other / "workspace/default", other / "model"
            monkeypatch.chdir(other)
            if stop == "timeout":
                deadline.reschedule(asyncio.get_running_loop().time() + 0.1)
            if stop == "cancel":
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
            await asyncio.sleep(0.15 if stop == "timeout" else 0)
            assert not task.done()
            hold.release.set()
            outcome, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            assert hold.finished.is_set() and not hold.expired
            if failure != "none":
                assert outcome is state["failure"]
            elif stop != "none":
                assert isinstance(outcome, asyncio.CancelledError if stop == "cancel" else TimeoutError)
            else:
                assert len(outcome.adoptions) == 2
            rows = [row for row in await records(first / "workspace/default/orket.log") if row["event"] == TARGET]
            assert len(rows) == int(failure != "before")
            if rows:
                assert rows[0]["data"]["department"] == state["expected"]["department"]
                assert rows[0]["timestamp"].endswith("-07:00")
            current = await asyncio.to_thread(contents, first)
            assert bool(json.loads(current["core/epics/unplanned_support.json"])["issues"]) is (failure == "none")
            assert await asyncio.to_thread(contents, other) == original_other
            assert not await records(other / "workspace/default/orket.log")
        finally:
            hold.release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
