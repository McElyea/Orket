"""Layer: integration. Retained coordinator transitions with real SQLite and workers."""
import asyncio
import threading

import httpx
import pytest

from orket.application.services.coordinator_runtime_service import CoordinatorUnavailableError
from orket.application.services.coordinator_store import InMemoryCoordinatorStore
from orket.core.domain import LeaseStatus
from tests.helpers.coordinator import Inputs, app_for, client_for
from tests.helpers.coordinator_server import coordinator_server

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class HeldClaimStore(InMemoryCoordinatorStore):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()

    def claim(self, *args, **kwargs):
        try:
            card = super().claim(*args, **kwargs)
            self.entered.set()
            assert self.release.wait(5)
            return card
        finally:
            self.finished.set()


async def test_concurrent_renew_waits_for_claim_publication(tmp_path):
    store = HeldClaimStore()
    app = app_for(tmp_path, store=store)
    owner = app.state.coordinator
    async with client_for(app) as client:
        claimed = asyncio.create_task(client.post("/cards/card/claim", json={"node_id": "node", "lease_duration": 20}))
        renewed = None
        try:
            assert await asyncio.to_thread(store.entered.wait, 5)
            renewed = asyncio.create_task(client.post("/cards/card/renew", json={"node_id": "node", "lease_duration": 60}))
            await asyncio.sleep(0)
            assert not claimed.done() and not renewed.done()
            assert await owner.repository.get_latest_lease_record(lease_id="coordinator-lease:card") is None
        finally:
            store.release.set()
            responses = await asyncio.wait_for(asyncio.gather(claimed, *([] if renewed is None else [renewed])), 5)
            await owner.close()
    assert len(responses) == 2 and all(response.status_code == 200 for response in responses)
    history = await owner.repository.list_lease_records(lease_id="coordinator-lease:card")
    assert len(history) == 2 and all(row.status is LeaseStatus.ACTIVE for row in history)
    assert history[-1].publication_timestamp > history[0].publication_timestamp
    assert owner.store.snapshot_card("card").lease_expires_at == 1060


async def test_cancelled_close_waiter_retains_transition_and_closes_owner(tmp_path):
    store = HeldClaimStore()
    owner = app_for(tmp_path, store=store).state.coordinator
    claimed = asyncio.create_task(owner.execute("claim", card_id="card", node_id="node", lease_duration=20))
    closing = None
    try:
        assert await asyncio.to_thread(store.entered.wait, 5)
        closing = asyncio.create_task(owner.close())
        await asyncio.sleep(0)
        closing.cancel()
        await asyncio.sleep(0)
        closing.cancel()
        await asyncio.sleep(0)
        assert not closing.done() and not owner.closed and not store.finished.is_set()
        with pytest.raises(CoordinatorUnavailableError):
            await asyncio.wait_for(owner.execute("list"), 0.5)
    finally:
        store.release.set()
        await asyncio.wait_for(claimed, 5)
        if closing is not None:
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(closing, 5)
        await owner.close()
    lease = await owner.repository.get_latest_lease_record(lease_id="coordinator-lease:card")
    assert owner.closed and store.finished.is_set() and lease.status is LeaseStatus.ACTIVE


async def test_publication_failure_survives_repeated_request_cancellation(tmp_path, monkeypatch):
    owner = app_for(tmp_path).state.coordinator
    entered, release = asyncio.Event(), asyncio.Event()
    original = owner.publication.publish_lease

    async def failed_publication(**kwargs):
        await original(**kwargs)
        entered.set()
        await release.wait()
        raise OSError("injected after retained real lease write")

    monkeypatch.setattr(owner.publication, "publish_lease", failed_publication)
    task = asyncio.create_task(owner.execute("claim", card_id="card", node_id="node", lease_duration=20))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(OSError, match="retained real lease write"):
            await asyncio.wait_for(task, 5)
        with pytest.raises(RuntimeError, match="failed transition"):
            await owner.close()
    with pytest.raises(CoordinatorUnavailableError):
        await owner.execute("list")
    lease = await owner.repository.get_latest_lease_record(lease_id="coordinator-lease:card")
    assert lease.status is LeaseStatus.ACTIVE and not owner.closed
    assert owner.store.snapshot_card("card").state == "CLAIMED"


async def test_descendant_cannot_deadlock_its_own_owner_close(tmp_path, monkeypatch):
    owner = app_for(tmp_path).state.coordinator
    original = owner.publication.publish_lease

    async def guarded_publication(**kwargs):
        with pytest.raises(RuntimeError, match="cannot await its own close"):
            await asyncio.wait_for(asyncio.create_task(owner.close()), 0.5)
        return await original(**kwargs)

    monkeypatch.setattr(owner.publication, "publish_lease", guarded_publication)
    try:
        claimed = await asyncio.wait_for(owner.execute("claim", card_id="card", node_id="node", lease_duration=20), 5)
        assert claimed.state == "CLAIMED"
    finally:
        await owner.close()
    assert owner.closed


async def test_public_expiry_reclaim_and_fail_publish_real_history(tmp_path):
    inputs = Inputs()
    app = app_for(tmp_path, inputs=inputs)
    owner = app.state.coordinator
    try:
        async with client_for(app) as client:
            first = await client.post("/cards/card/claim", json={"node_id": "first", "lease_duration": 2})
            assert first.status_code == 200
            inputs.elapsed = 1003
            second = await client.post("/cards/card/claim", json={"node_id": "second", "lease_duration": 20})
            assert second.status_code == 200 and second.json()["claimed_by"] == "second"
            failed = await client.post("/cards/card/fail", json={"node_id": "second", "result": {"reason": "observed"}})
            assert failed.status_code == 200 and failed.json()["state"] == "FAILED"
    finally:
        await owner.close()
    history = await owner.repository.list_lease_records(lease_id="coordinator-lease:card")
    assert [row.status for row in history] == [LeaseStatus.ACTIVE, LeaseStatus.EXPIRED, LeaseStatus.ACTIVE, LeaseStatus.RELEASED]
    assert [row.lease_epoch for row in history] == [1, 1, 2, 2]
    assert owner.store.snapshot_card("card").result == {"reason": "observed"}


async def test_reversed_wall_time_is_refused_without_clamping(tmp_path):
    inputs = Inputs()
    app = app_for(tmp_path, inputs=inputs)
    owner = app.state.coordinator
    async with client_for(app, raise_errors=False) as client:
        claimed = await client.post("/cards/card/claim", json={"node_id": "node", "lease_duration": 20})
        assert claimed.status_code == 200
        inputs.tick = -10
        renewed = await client.post("/cards/card/renew", json={"node_id": "node", "lease_duration": 60})
        assert renewed.status_code == 500
        assert (await client.get("/cards")).status_code == 503
    with pytest.raises(RuntimeError, match="failed transition"):
        await owner.close()
    history = await owner.repository.list_lease_records(lease_id="coordinator-lease:card")
    assert len(history) == 1 and history[0].publication_timestamp == "2026-09-18T00:00:01+00:00"
    assert owner.store.snapshot_card("card").lease_expires_at == 1060 and not owner.closed


async def test_real_http_server_runs_coordinator_and_lifespan_close(tmp_path):
    app = app_for(tmp_path)
    owner = app.state.coordinator
    async with coordinator_server(app) as url, httpx.AsyncClient(base_url=url, trust_env=False) as client:
        listed = await client.get("/cards")
        assert listed.status_code == 200 and listed.json()[0]["state"] == "OPEN"
        claimed = await client.post("/cards/card/claim", json={"node_id": "node", "lease_duration": 20})
        assert claimed.status_code == 200
        completed = await client.post("/cards/card/complete", json={"node_id": "node", "result": {"ok": True}})
        assert completed.status_code == 200 and completed.json()["state"] == "DONE"
    lease = await owner.repository.get_latest_lease_record(lease_id="coordinator-lease:card")
    assert owner.closed and lease.status is LeaseStatus.RELEASED
