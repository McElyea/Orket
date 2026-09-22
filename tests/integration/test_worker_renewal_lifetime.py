"""Layer: integration. Actual HTTP/SQLite effects and owned native renewal threads."""
import asyncio
import time

import aiosqlite
import httpx
import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.core.domain import LeaseStatus
from tests.helpers.worker_lifetime import start_work, worker_lifetime

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _responsive(rig, root, record_property):
    started = time.perf_counter()
    async with aiosqlite.connect(root / "unrelated.sqlite3") as connection:
        assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
    latency = time.perf_counter() - started
    record_property("worker_sqlite_latency_seconds", latency)
    assert latency < 0.5
    async with httpx.AsyncClient(base_url=rig.url, trust_env=False, timeout=2) as client:
        response = await client.get("/cards")
        assert response.status_code == 200 and response.json() == []
        assert rig.owner.store.snapshot_card("card").state == "CLAIMED"


async def _assert_settled(rig, *, completed):
    assert rig.finished.is_set() and not rig.thread.is_alive()
    assert not rig.client.is_closed
    listed = await run_owned_thread(lambda: rig.client.get("/cards"), label="fixture-borrowed-client-still-usable")
    assert listed.status_code == 200
    lease = await rig.owner.repository.get_latest_lease_record(lease_id="coordinator-lease:card")
    assert lease.status is (LeaseStatus.RELEASED if completed else LeaseStatus.ACTIVE)
    assert rig.owner.store.snapshot_card("card").state == ("DONE" if completed else "CLAIMED")


async def test_work_failure_retains_real_renewal_before_return(tmp_path, record_property):
    async with worker_lifetime(tmp_path, work_failure=True) as rig:
        task = start_work(rig)
        assert await asyncio.to_thread(rig.entered.wait, 5)
        await asyncio.sleep(0.08)
        assert not task.done() and not rig.finished.is_set()
        await _responsive(rig, tmp_path, record_property)
        rig.release.set()
        with pytest.raises(ValueError, match="work failed during real renewal"):
            await asyncio.wait_for(asyncio.shield(task), 5)
        await _assert_settled(rig, completed=False)


@pytest.mark.parametrize("work_failure", [False, True], ids=["renewal-failure", "both-fail"])
@pytest.mark.parametrize("interrupt", [False, True], ids=["normal-waiter", "repeated-cancel"])
async def test_real_renewal_failure_surfaces_before_completion(tmp_path, work_failure, interrupt):
    async with worker_lifetime(tmp_path, work_failure=work_failure, renew_failure=True) as rig:
        task = start_work(rig)
        assert await asyncio.to_thread(rig.entered.wait, 5)
        if work_failure:
            assert await asyncio.to_thread(rig.work_failed.wait, 5)
        if interrupt:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        rig.release.set()
        with pytest.raises(OSError, match="renewal failed after real HTTP acceptance") as failure:
            await asyncio.wait_for(asyncio.shield(task), 5)
        if work_failure:
            assert isinstance(failure.value.__context__, ValueError)
            assert "work failed during real renewal" in str(failure.value.__context__)
        await _assert_settled(rig, completed=False)


@pytest.mark.parametrize("interrupt", ["none", "cancel", "repeated-cancel", "timeout"])
async def test_owned_worker_retains_held_http_and_finishes_threads(tmp_path, record_property, interrupt):
    async with worker_lifetime(tmp_path) as rig:
        task = start_work(rig, timeout=interrupt == "timeout")
        assert await asyncio.to_thread(rig.entered.wait, 5)
        if "cancel" in interrupt:
            task.cancel()
            await asyncio.sleep(0)
            if interrupt == "repeated-cancel":
                task.cancel()
        await asyncio.sleep(0.2)
        assert not task.done() and not rig.finished.is_set()
        await _responsive(rig, tmp_path, record_property)
        rig.release.set()
        if interrupt == "none":
            result = await asyncio.wait_for(asyncio.shield(task), 5)
            assert result.status_code == 200 and result.json()["result"] == {"worker": "worker"}
        else:
            error = TimeoutError if interrupt == "timeout" else asyncio.CancelledError
            with pytest.raises(error):
                await asyncio.wait_for(asyncio.shield(task), 5)
        await _assert_settled(rig, completed=True)
