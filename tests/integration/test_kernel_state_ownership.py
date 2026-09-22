"""Layer: integration. Actual state publication stays within its admitted lifetime."""

import asyncio
import json
import threading
from functools import partial

import httpx
import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage import kernel_state_store as store
from orket.application.services.kernel_invocation_service import invoke_kernel
from orket.application.services.kernel_runtime_lifetime import KernelRuntimeLifetime
from orket.application.services.kernel_v1_gateway import KernelV1Gateway
from tests.helpers.kernel_capability_probe import turn_request
from tests.helpers.kernel_state_probe import kernel_app, responsive_sqlite
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.integration.test_kernel_state_effect_boundaries import tree

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def promotion_request():
    request = turn_request("unused")
    request.update(turn_id="turn-0001", commit_intent="stage_and_request_promotion")
    return request


@pytest.mark.parametrize("boundary", ["stage", "promotion"])
@pytest.mark.parametrize("interruption", ["cancel", "timeout"])
async def test_held_state_effects_stay_owned_through_shutdown(
    tmp_path, monkeypatch, record_property, boundary, interruption
):
    gateway = KernelV1Gateway(invocation_root=tmp_path)
    lifetime = KernelRuntimeLifetime(gateway.runtime)
    entered, release = threading.Event(), threading.Event()
    name = "write_bytes" if boundary == "stage" else "copy_file"
    original, observed = getattr(store, name), []

    def held(*args):
        if not entered.is_set():
            entered.set()
            assert release.wait(10), "state effect was not released"
        result = original(*args)
        observed.append((threading.get_ident(), gateway.runtime.closed))
        return result

    monkeypatch.setattr(store, name, held)
    active = asyncio.create_task(
        lifetime.invoke(
            partial(
                invoke_kernel,
                gateway.run_lifecycle,
                workflow_id="owned-state",
                execute_turn_requests=[promotion_request()],
            )
        )
    )
    closing = waiter = None
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 10), 10)
        closing = asyncio.create_task(lifetime.close())
        if interruption == "timeout":
            waiter = asyncio.create_task(asyncio.wait_for(active, 0.02))
        else:
            active.cancel()
            await asyncio.sleep(0)
            active.cancel()
        await asyncio.sleep(0.04)
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        assert not active.done() and not closing.done() and not gateway.runtime.closed
        release.set()
        outcomes = await asyncio.wait_for(
            asyncio.gather(active, closing, *([waiter] if waiter else []), return_exceptions=True), 10
        )
        assert isinstance(outcomes[0], asyncio.CancelledError) and outcomes[1] is None
        if waiter:
            assert isinstance(outcomes[2], TimeoutError)
        assert observed and all(worker != threading.get_ident() and not closed for worker, closed in observed)
        assert gateway.runtime.closed and lifetime.active_request_count == 0
        root = tmp_path / ".orket_kernel/index"
        persisted = await asyncio.to_thread(tree, root)
        assert "committed/triplets/fixture.json" in persisted
        assert json.loads(persisted["committed/index/run_ledger.json"][0])["last_promoted_turn_id"] == "turn-0001"
        assert not any(".__new/" in name or ".__bak/" in name or name.startswith("staging/") for name in persisted)
        await asyncio.sleep(0.04)
        assert await asyncio.to_thread(tree, root) == persisted
    finally:
        release.set()
        await asyncio.gather(
            active, *([closing] if closing else []), *([waiter] if waiter else []), return_exceptions=True
        )
        await run_owned_thread(gateway.close, label="state-fixture-close")


async def test_staging_failure_survives_cancellation_and_close(tmp_path, monkeypatch, record_property):
    gateway = KernelV1Gateway(invocation_root=tmp_path)
    lifetime = KernelRuntimeLifetime(gateway.runtime)
    entered, release = threading.Event(), threading.Event()
    failure = OSError("native staging write failed")

    def failed_write(*_args):
        entered.set()
        assert release.wait(10), "failing staging write was not released"
        raise failure

    monkeypatch.setattr(store, "write_bytes", failed_write)
    active = asyncio.create_task(
        lifetime.invoke(
            partial(
                invoke_kernel,
                gateway.run_lifecycle,
                workflow_id="failed-state",
                execute_turn_requests=[promotion_request()],
            )
        )
    )
    closing = None
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 10), 10)
        active.cancel()
        await asyncio.sleep(0)
        active.cancel()
        closing = asyncio.create_task(lifetime.close())
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        assert not active.done() and not closing.done()
        release.set()
        outcomes = await asyncio.wait_for(asyncio.gather(active, closing, return_exceptions=True), 10)
        assert outcomes[0] is failure
        assert isinstance(outcomes[1], RuntimeError) and outcomes[1].__cause__ is failure
        assert gateway.runtime.closed and lifetime.active_request_count == 0
        assert not await asyncio.to_thread((tmp_path / ".orket_kernel").exists)
    finally:
        release.set()
        await asyncio.gather(active, *([closing] if closing else []), return_exceptions=True)
        await run_owned_thread(gateway.close, label="failed-state-fixture-close")


async def test_authenticated_api_promotion_then_noop_preserves_committed_triplet(tmp_path, monkeypatch):
    app = kernel_app(tmp_path)
    write, workers = store.write_bytes, []

    def observed_write(*args):
        workers.append(threading.get_ident())
        return write(*args)

    monkeypatch.setattr(store, "write_bytes", observed_write)
    async with app.router.lifespan_context(app):
        owner = app.state.api_runtime_context
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://api.test") as client:
            noop = {"turn_id": "turn-0002", "turn_input": {}, "commit_intent": "stage_and_request_promotion"}
            response = await client.post(
                "/v1/kernel/lifecycle",
                headers={"X-API-Key": TEST_API_KEY},
                json={"workflow_id": "state-promotion", "execute_turn_requests": [promotion_request(), noop]},
            )
            assert response.status_code == 200, response.text
            turns = response.json()["turns"]
            assert [turn["outcome"] for turn in turns] == ["PASS", "PASS"]
            assert any("I_NOOP_PROMOTION" in event for event in turns[1]["events"])
            persisted = await asyncio.to_thread(tree, tmp_path / ".orket_kernel/index/committed")
            assert "triplets/fixture.json" in persisted
            assert json.loads(persisted["index/run_ledger.json"][0])["last_promoted_turn_id"] == "turn-0002"
            assert workers and all(worker != threading.get_ident() for worker in workers)
    assert owner.closed and owner.engine.kernel_gateway.runtime.closed
