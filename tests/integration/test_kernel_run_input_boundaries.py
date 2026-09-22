"""Real Kernel start/staging boundaries under selected identity and changing cwd."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

import orket.application.services.kernel_capability_policy_service as policy_service
import orket.application.services.kernel_invocation_service as invocation_service
from orket.application.services.kernel_v1_gateway import KernelV1Gateway
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.kernel.v1 import api
from tests.helpers.kernel_capability_probe import turn_request
from tests.helpers.kernel_state_probe import kernel_app
from tests.helpers.outward_authorization import TEST_API_KEY

pytestmark = pytest.mark.integration


class SelectedInputs(RuntimeInputService):
    def create_kernel_run_id(self):
        return "run-selected-input"


def roots(tmp_path):
    initial, later = tmp_path / "initial", tmp_path / "later"
    initial.mkdir()
    later.mkdir()
    return initial, later


def test_gateway_start_uses_selected_run_identity():
    gateway = KernelV1Gateway(runtime_inputs=SelectedInputs())
    try:
        result = gateway.start_run({"contract_version": "kernel_api/v1", "workflow_id": "selected"})
        assert result["run_handle"]["run_id"] == "run-selected-input"
    finally:
        gateway.close()


def test_run_handle_keeps_gateway_root_across_cwd_changes(tmp_path, monkeypatch):
    initial, later = roots(tmp_path)
    monkeypatch.chdir(initial)
    gateway = KernelV1Gateway()
    try:
        start = gateway.start_run(
            {"contract_version": "kernel_api/v1", "workflow_id": "rooted", "workspace_root": "run-space"}
        )
        monkeypatch.chdir(later)
        request = turn_request("unused")
        request["run_handle"] = start["run_handle"]
        result = gateway.execute_turn(request)
        assert result["outcome"] == "PASS"
        assert list((initial / "run-space").rglob("fixture.json"))
        assert not (later / "run-space").exists()
        assert Path(start["run_handle"]["workspace_root"]) == initial / "run-space"
    finally:
        gateway.close()


def test_direct_turn_binds_root_before_policy_read(tmp_path, monkeypatch):
    initial, later = roots(tmp_path)
    monkeypatch.chdir(initial)
    entered, release = threading.Event(), threading.Event()
    read = policy_service.read_kernel_capability_policy

    def held(path):
        payload = read(path)
        entered.set()
        assert release.wait(10), "held policy read was not released"
        return payload

    monkeypatch.setattr(policy_service, "read_kernel_capability_policy", held)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(api.execute_turn, turn_request("run-space"))
        try:
            assert entered.wait(10)
            monkeypatch.chdir(later)
            release.set()
            assert pending.result(timeout=10)["outcome"] == "PASS"
            assert list((initial / "run-space").rglob("fixture.json"))
            assert not (later / "run-space").exists()
        finally:
            release.set()


@pytest.mark.asyncio
async def test_queued_direct_invocation_keeps_admitted_root(tmp_path, monkeypatch):
    initial, later = roots(tmp_path)
    monkeypatch.chdir(initial)
    entered, release = asyncio.Event(), asyncio.Event()
    dispatch = invocation_service.run_owned_thread

    async def held(operation, *, label):
        entered.set()
        await release.wait()
        return await dispatch(operation, label=label)

    monkeypatch.setattr(invocation_service, "run_owned_thread", held)
    task = asyncio.create_task(invocation_service.invoke_kernel(api.execute_turn, turn_request("run-space")))
    try:
        await asyncio.wait_for(entered.wait(), 10)
        monkeypatch.chdir(later)
        release.set()
        assert (await asyncio.wait_for(task, 10))["outcome"] == "PASS"
        assert await asyncio.to_thread(lambda: bool(list((initial / "run-space").rglob("fixture.json"))))
        assert not await asyncio.to_thread((later / "run-space").exists)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_api_default_workspace_belongs_to_selected_application(tmp_path, monkeypatch):
    initial, later = roots(tmp_path)
    monkeypatch.chdir(later)
    app = kernel_app(initial)
    async with app.router.lifespan_context(app):
        owner = app.state.api_runtime_context
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://api.test") as client:
            response = await client.post(
                "/v1/kernel/lifecycle",
                headers={"X-API-Key": TEST_API_KEY},
                json={
                    "workflow_id": "root-proof",
                    "execute_turn_requests": [turn_request("unused")],
                },
            )
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["turns"][0]["outcome"] == "PASS"
            assert Path(result["start"]["run_handle"]["workspace_root"]) == initial / ".orket_kernel"
            assert await asyncio.to_thread(lambda: bool(list((initial / ".orket_kernel").rglob("fixture.json"))))
            assert not await asyncio.to_thread((later / ".orket_kernel").exists)
    assert owner.closed and owner.engine.kernel_gateway.runtime.closed
