"""Layer: integration. Isolated coordinator applications, real store transitions and SQLite."""
import asyncio
import json
import os
import sys
import threading
from pathlib import Path

import pytest

import orket.interfaces.coordinator_api as coordinator_api
from orket.application.services.coordinator_store import InMemoryCoordinatorStore
from orket.core.domain import LeaseStatus, ReservationStatus
from tests.helpers.coordinator import Inputs, app_for, client_for

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_import_and_factory_do_not_create_durable_state(tmp_path):
    import orket

    environment = dict(os.environ, ORKET_DURABLE_ROOT=str(tmp_path / "durable"),
                       PYTHONPATH=str(Path(orket.__file__).parent.parent), ORKET_DISABLE_SANDBOX="1")
    code = ("import json;import orket.interfaces.coordinator_api as m;"
            "print(json.dumps({'origin':m.__file__,'owners':[n for n in "
            "('app','store','control_plane_repository') if hasattr(m,n)]}))")
    process = await asyncio.create_subprocess_exec(sys.executable, "-c", code, cwd=tmp_path, env=environment,
                                                   stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        output, error = await asyncio.wait_for(process.communicate(), 30)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert process.returncode == 0, error.decode()
    report = json.loads(output)
    assert report["origin"] == coordinator_api.__file__ and report["owners"] == []
    assert not (tmp_path / "durable").exists()
    app = app_for(tmp_path)
    assert not (tmp_path / ".orket").exists()
    await app.state.coordinator.close()
    assert app.state.coordinator.closed


async def test_public_claim_renew_complete_and_roots_use_captured_inputs(tmp_path, monkeypatch):
    inputs, environment = Inputs(), {"ORKET_DURABLE_ROOT": "selected"}
    first, second = app_for(tmp_path / "first", inputs=inputs, environment=environment), app_for(tmp_path / "second")
    environment["ORKET_DURABLE_ROOT"] = "changed"
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / "ambient"))
    try:
        async with client_for(first) as client, client_for(second) as other:
            claim = await client.post("/cards/card/claim", json={"node_id": "node", "lease_duration": 20})
            assert claim.status_code == 200
            body = claim.json()
            assert body["lease_expires_at"] == 1020
            assert body["control_plane_lease"]["publication_timestamp"] == "2026-09-18T00:00:01+00:00"
            assert body["control_plane_reservation"]["status"] == ReservationStatus.PROMOTED_TO_LEASE.value
            assert (await other.get("/cards")).json()[0]["state"] == "OPEN"
            inputs.elapsed = 1002
            renewed = await client.post("/cards/card/renew", json={"node_id": "node", "lease_duration": 30})
            assert renewed.status_code == 200 and renewed.json()["lease_expires_at"] == 1032
            completed = await client.post("/cards/card/complete", json={"node_id": "node", "result": {"nested": [1]}})
            assert completed.status_code == 200 and completed.json()["state"] == "DONE"
            assert completed.json()["control_plane_lease"]["status"] == LeaseStatus.RELEASED.value
            assert (await client.get("/cards")).json() == []
    finally:
        await asyncio.gather(first.state.coordinator.close(), second.state.coordinator.close())
    assert (tmp_path / "first/selected/db/control_plane_records.sqlite3").is_file()
    assert not (tmp_path / "first/changed").exists() and not (tmp_path / "ambient").exists()


async def test_cancelled_claim_and_shutdown_retain_real_publication(tmp_path):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    class HeldStore(InMemoryCoordinatorStore):
        def claim(self, *args, **kwargs):
            try:
                result = super().claim(*args, **kwargs)
                entered.set()
                assert release.wait(5)
                return result
            finally:
                finished.set()

    app = app_for(tmp_path, store=HeldStore())
    owner = app.state.coordinator
    async with client_for(app) as client:
        task = asyncio.create_task(client.post("/cards/card/claim", json={"node_id": "node", "lease_duration": 60}))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            closing = asyncio.create_task(owner.close())
            await asyncio.sleep(0)
            assert not task.done() and not closing.done() and not finished.is_set()
            unavailable = await asyncio.wait_for(client.get("/cards"), 0.5)
            assert unavailable.status_code == 503
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
            await asyncio.wait_for(owner.close(), 5)
            if "closing" in locals():
                await asyncio.wait_for(closing, 5)
    lease = await owner.repository.get_latest_lease_record(lease_id="coordinator-lease:card")
    reservation = await owner.repository.get_latest_reservation_record(reservation_id=lease.source_reservation_id)
    assert owner.closed and finished.is_set() and lease.status is LeaseStatus.ACTIVE
    assert reservation.status is ReservationStatus.PROMOTED_TO_LEASE and owner.store.snapshot_card("card").state == "CLAIMED"


@pytest.mark.parametrize("kind", ["complete", "fail"])
async def test_completion_captures_nested_result_before_await_and_after_return(tmp_path, kind):
    entered, release = threading.Event(), threading.Event()

    class HeldStore(InMemoryCoordinatorStore):
        hold = False

        def snapshot_card(self, card_id):
            row = super().snapshot_card(card_id)
            if self.hold:
                entered.set()
                assert release.wait(5)
            return row

    store = HeldStore()
    owner = app_for(tmp_path, store=store).state.coordinator
    await owner.execute("claim", card_id="card", node_id="node", lease_duration=60)
    result = {"nested": {"state": "captured"}}
    store.hold = True
    task = asyncio.create_task(owner.execute(kind, card_id="card", node_id="node", result=result))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        result["nested"]["state"] = "changed-while-awaiting"
    finally:
        release.set()
        completed = await asyncio.wait_for(task, 5)
        await owner.close()
    result["nested"]["state"] = "changed-after-return"
    assert completed.result == store.snapshot_card("card").result == {"nested": {"state": "captured"}}


async def test_publication_failure_is_retained_and_closes_admission(tmp_path, monkeypatch):
    app = app_for(tmp_path)
    owner = app.state.coordinator
    original = owner.publication.publish_lease

    async def failed_publication(**kwargs):
        await original(**kwargs)
        raise OSError("injected after real lease write")

    monkeypatch.setattr(owner.publication, "publish_lease", failed_publication)
    async with client_for(app, raise_errors=False) as client:
        failed = await client.post("/cards/card/claim", json={"node_id": "node", "lease_duration": 60})
        assert failed.status_code == 500
        assert (await client.get("/cards")).status_code == 503
    with pytest.raises(RuntimeError, match="failed transition"):
        await owner.close()
    assert not owner.closed and owner.store.snapshot_card("card").state == "CLAIMED"
    assert await owner.repository.get_latest_lease_record(lease_id="coordinator-lease:card") is not None


@pytest.mark.parametrize("duration", [float("nan"), float("inf"), float("-inf")])
async def test_nonfinite_duration_is_rejected_before_card_mutation(tmp_path, duration):
    app = app_for(tmp_path)
    owner = app.state.coordinator
    try:
        async with client_for(app) as client:
            response = await client.post("/cards/card/claim", headers={"Content-Type": "application/json"},
                                         content=json.dumps({"node_id": "node", "lease_duration": duration}))
            assert response.status_code == 400
            assert response.json() == {"detail": "lease_duration must be finite"}
            assert owner.store.snapshot_card("card").state == "OPEN"
            assert await owner.repository.get_latest_lease_record(lease_id="coordinator-lease:card") is None
    finally:
        await owner.close()


async def test_nonfinite_observation_does_not_publish_expiry(tmp_path):
    inputs = Inputs()
    app = app_for(tmp_path, inputs=inputs)
    owner = app.state.coordinator
    try:
        async with client_for(app) as client:
            claimed = await client.post("/cards/card/claim", json={"node_id": "node", "lease_duration": 20})
            assert claimed.status_code == 200
            inputs.elapsed = float("nan")
            listed = await client.get("/cards")
            assert listed.status_code == 400
            lease = await owner.repository.get_latest_lease_record(lease_id="coordinator-lease:card")
            assert lease.status is LeaseStatus.ACTIVE and owner.store.snapshot_card("card").state == "CLAIMED"
    finally:
        await owner.close()
