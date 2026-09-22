"""Layer: integration. Real policy I/O and staging stay owned through interruption."""

import asyncio
import json
import threading
from functools import partial

import httpx
import pytest

import orket.application.services.kernel_capability_policy_service as service
from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.kernel_invocation_service import invoke_kernel
from orket.application.services.kernel_runtime_lifetime import KernelRuntimeLifetime
from orket.application.services.kernel_v1_gateway import KernelV1Gateway
from tests.helpers.kernel_capability_probe import policy_payload, turn_request
from tests.helpers.kernel_state_probe import kernel_app, responsive_sqlite
from tests.helpers.outward_authorization import TEST_API_KEY

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("interruption", ["cancel", "timeout", "failure"])
async def test_policy_worker_drains_before_runtime_close(tmp_path, monkeypatch, record_property, interruption):
    path = tmp_path / "policy.json"
    await asyncio.to_thread(path.write_text, json.dumps(policy_payload()), encoding="utf-8")
    monkeypatch.setattr(service, "DEFAULT_KERNEL_CAPABILITY_POLICY_PATH", path)
    entered, release = threading.Event(), threading.Event()
    read, workers = service.read_kernel_capability_policy, []

    def held(selected):
        workers.append(threading.get_ident())
        entered.set()
        assert release.wait(10), "policy ownership fixture not released"
        return read(selected)

    monkeypatch.setattr(service, "read_kernel_capability_policy", held)
    gateway = KernelV1Gateway()
    lifetime = KernelRuntimeLifetime(gateway.runtime)
    root = tmp_path / "effect"
    active = asyncio.create_task(lifetime.invoke(partial(invoke_kernel, gateway.execute_turn, turn_request(root))))
    closing = waiter = None
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 10), 10)
        assert workers == [workers[0]] and workers[0] != threading.get_ident()
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
        if interruption == "failure":
            await asyncio.to_thread(path.unlink)
        release.set()
        outcomes = await asyncio.wait_for(
            asyncio.gather(active, closing, *([waiter] if waiter else []), return_exceptions=True), 10
        )
        if interruption == "failure":
            assert isinstance(outcomes[0], FileNotFoundError)
            assert isinstance(outcomes[1], RuntimeError) and outcomes[1].__cause__ is outcomes[0]
            assert not root.exists()
        else:
            assert isinstance(outcomes[0], asyncio.CancelledError) and outcomes[1] is None
            if waiter:
                assert isinstance(outcomes[2], TimeoutError)
            assert await asyncio.to_thread(lambda: bool(list(root.rglob("fixture.json"))))
        assert gateway.runtime.closed
    finally:
        release.set()
        await asyncio.gather(
            active, *([closing] if closing else []), *([waiter] if waiter else []), return_exceptions=True
        )
        await run_owned_thread(gateway.close, label="policy-fixture-close")


@pytest.mark.parametrize("action", ["file.write", "foreign.execute"])
async def test_lifecycle_http_uses_shipped_policy_and_actual_staging(tmp_path, action):
    app = kernel_app(tmp_path)
    root = tmp_path / "effect"
    request = turn_request(root)
    request["turn_input"]["tool_call"]["action"] = action
    async with app.router.lifespan_context(app):
        owner = app.state.api_runtime_context
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://api.test") as client:
            response = await client.post(
                "/v1/kernel/lifecycle",
                headers={"X-API-Key": TEST_API_KEY},
                json={
                    "workflow_id": "policy-proof",
                    "start_request": {"workspace_root": str(root)},
                    "execute_turn_requests": [request],
                },
            )
            assert response.status_code == 200, response.text
            turn = response.json()["turns"][0]
            assert turn["outcome"] == ("PASS" if action == "file.write" else "FAIL")
            decision = turn["capabilities"]["decisions"][0]
            assert decision["evidence"]["capability_source"] == "policy://orket/kernel/v1/default"
            assert await asyncio.to_thread(root.exists) == (action == "file.write")
            if action == "file.write":
                assert await asyncio.to_thread(lambda: bool(list(root.rglob("fixture.json"))))
    assert owner.closed and owner.engine.kernel_gateway.runtime.closed
