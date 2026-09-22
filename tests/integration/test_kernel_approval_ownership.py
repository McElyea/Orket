"""Layer: integration. Real approval resolution retains its required SQLite publication."""

import asyncio
import threading

import pytest

from orket.core.domain import ReservationStatus
from orket.kernel.v1 import nervous_system_approvals
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime
from tests.helpers.kernel_state_probe import hold_native, interrupt_owned, kernel_app, responsive_sqlite

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("credential_runtime")]


async def test_approval_worker_is_responsive(tmp_path, monkeypatch, record_property):
    app = kernel_app(tmp_path)
    async with app.router.lifespan_context(app):
        engine = app.state.api_runtime_context.engine
        admitted = await engine.kernel_admit_proposal_async(
            {
                "contract_version": "kernel_api/v1",
                "session_id": "approval-owned",
                "trace_id": "trace",
                "proposal": {"proposal_type": "action.tool_call", "payload": {"approval_required_credentialed": True}},
            }
        )
        hold = hold_native(monkeypatch, nervous_system_approvals, "_normalize_decision")
        task = asyncio.create_task(engine.decide_approval(approval_id=admitted["approval_id"], decision="approve"))
        try:
            assert await asyncio.wait_for(asyncio.to_thread(hold.entered.wait, 10), 10)
            await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
            assert hold.worker != threading.get_ident() and not hold.expired
            hold.release.set()
            assert (await asyncio.wait_for(task, 10))["approval"]["status"] == "APPROVED"
        finally:
            hold.release.set()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("timed", [False, True], ids=["repeated-cancel", "timeout"])
async def test_approval_resolution_keeps_sqlite_hold_release(tmp_path, monkeypatch, timed):
    app = kernel_app(tmp_path)
    async with app.router.lifespan_context(app):
        engine = app.state.api_runtime_context.engine
        admitted = await engine.kernel_admit_proposal_async(
            {
                "contract_version": "kernel_api/v1",
                "session_id": "approval-owned",
                "trace_id": "trace",
                "proposal": {"proposal_type": "action.tool_call", "payload": {"approval_required_credentialed": True}},
            }
        )
        entered, release = asyncio.Event(), asyncio.Event()
        original = engine.control_plane_publication.release_reservation

        async def held(**kwargs):
            entered.set()
            await release.wait()
            return await original(**kwargs)

        monkeypatch.setattr(engine.control_plane_publication, "release_reservation", held)
        task = asyncio.create_task(engine.decide_approval(approval_id=admitted["approval_id"], decision="approve"))
        waiter = task
        try:
            await asyncio.wait_for(entered.wait(), 10)
            waiter = await interrupt_owned(task, release, timed=timed)
            with pytest.raises(TimeoutError if timed else asyncio.CancelledError):
                await asyncio.wait_for(waiter, 10)
            approved = await engine.get_approval(admitted["approval_id"])
            reservation = await engine.control_plane_repository.get_latest_reservation_record(
                reservation_id="approval-reservation:" + admitted["approval_id"]
            )
            assert approved["status"] == "APPROVED" and reservation.status is ReservationStatus.RELEASED
        finally:
            release.set()
            await asyncio.gather(task, waiter, return_exceptions=True)
