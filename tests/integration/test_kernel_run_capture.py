"""Real native boundaries retain selected run inputs and borrowed lifecycle data."""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.kernel_invocation_inputs import (
    bind_kernel_invocation_root,
    capture_kernel_invocation_root,
)
from orket.application.services.kernel_runtime_owner import KernelRuntime
from orket.application.services.kernel_v1_gateway import KernelV1Gateway
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.kernel.v1 import api
from tests.helpers.kernel_capability_probe import turn_request
from tests.helpers.kernel_runtime import ObservedKernelLock

pytestmark = pytest.mark.integration


class SelectedInputs(RuntimeInputService):
    def __init__(self, callback):
        self.callback = callback
        self.calls = 0

    def create_kernel_run_id(self):
        self.calls += 1
        return self.callback()


def test_start_captures_request_and_root_before_selected_identity_callback(tmp_path, monkeypatch):
    later = tmp_path / "later"
    later.mkdir()
    request = {
        "contract_version": "kernel_api/v1",
        "workflow_id": "captured",
        "workspace_root": "work",
        "visibility_mode": "local_offline",
    }

    def selected():
        request.update(workspace_root="mutated", visibility_mode="local_only")
        monkeypatch.chdir(later)
        return "run-selected"

    source = SelectedInputs(selected)
    gateway = KernelV1Gateway(runtime_inputs=source, invocation_root=tmp_path)
    monkeypatch.setattr(source, "create_kernel_run_id", lambda: pytest.fail("selected method was replaced"))
    try:
        result = gateway.start_run(request)
        assert result["run_handle"] == {
            "contract_version": "kernel_api/v1",
            "run_id": "run-selected",
            "workspace_root": str(tmp_path / "work"),
            "visibility_mode": "local_offline",
        }
        assert source.calls == 1 and not (tmp_path / "work").exists()
    finally:
        gateway.close()


@pytest.mark.parametrize("value", [None, "", 7, False])
def test_invalid_selected_identity_refuses_without_fallback_or_files(tmp_path, value):
    source = SelectedInputs(lambda: value)
    gateway = KernelV1Gateway(runtime_inputs=source, invocation_root=tmp_path)
    try:
        with pytest.raises(ValueError, match="E_KERNEL_RUN_ID_NONEMPTY_STRING_REQUIRED"):
            gateway.run_lifecycle(workflow_id="invalid", execute_turn_requests=[turn_request("unused")])
        assert source.calls == 1 and list(tmp_path.iterdir()) == []
    finally:
        gateway.close()


def test_identity_failure_and_invalid_request_do_not_mint_another_identity(tmp_path):
    failure = OSError("selected identity unavailable")

    def refused():
        raise failure

    source = SelectedInputs(refused)
    gateway = KernelV1Gateway(runtime_inputs=source, invocation_root=tmp_path)
    try:
        with pytest.raises(ValueError, match="workflow_id"):
            gateway.start_run({"contract_version": "kernel_api/v1"})
        assert source.calls == 0
        with pytest.raises(OSError) as observed:
            gateway.start_run({"contract_version": "kernel_api/v1", "workflow_id": "failure"})
        assert observed.value is failure and source.calls == 1
        assert list(tmp_path.iterdir()) == []
    finally:
        gateway.close()


def test_whole_lifecycle_captures_turn_list_before_start_waits(tmp_path, monkeypatch):
    gateway = KernelV1Gateway(invocation_root=tmp_path)
    entered, release = threading.Event(), threading.Event()
    start = gateway.start_run

    def held(request):
        entered.set()
        assert release.wait(10), "start callback was not released"
        return start(request)

    monkeypatch.setattr(gateway, "start_run", held)
    requests = [turn_request("unused")]
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(gateway.run_lifecycle, workflow_id="capture", execute_turn_requests=requests)
        try:
            assert entered.wait(10)
            requests[0]["turn_input"]["stage_triplet"]["body"]["value"] = "changed-during-start"
            requests.clear()
            release.set()
            result = pending.result(timeout=10)
            assert len(result["turns"]) == 1 and result["turns"][0]["outcome"] == "PASS"
            assert all(b"changed-during-start" not in p.read_bytes() for p in tmp_path.rglob("*") if p.is_file())
            assert list(tmp_path.rglob("fixture.json"))
        finally:
            release.set()
            pending.result(timeout=10)
            gateway.close()


@pytest.mark.asyncio
async def test_implicit_start_requires_native_owner_and_json_cannot_replace_inputs(tmp_path):
    request = {
        "contract_version": "kernel_api/v1",
        "workflow_id": "owner",
        "run_inputs": {"run_id": "wire-injection", "workspace": {"root": "foreign"}},
    }
    with pytest.raises(RuntimeError, match="E_KERNEL_INVOCATION_REQUIRES_ASYNC_OWNER"):
        api.start_run(request)
    with pytest.raises(RuntimeError, match="E_KERNEL_RUNTIME_OWNER_REQUIRED"):
        await run_owned_thread(lambda: api.start_run(request), label="unbound-start")
    source = SelectedInputs(lambda: "run-owned")
    async with KernelRuntime.open(runtime_inputs=source, invocation_root=tmp_path) as owner:
        result = await run_owned_thread(lambda: api.start_run(request), label="bound-start")
        assert result["run_handle"]["run_id"] == "run-owned" and source.calls == 1
    assert owner.closed


def test_root_context_is_immutable_nested_and_does_not_resolve_links(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = capture_kernel_invocation_root("first/../selected")
    assert first.root == str(tmp_path / "first/../selected")
    with bind_kernel_invocation_root(first):
        assert capture_kernel_invocation_root() is first
        nested = capture_kernel_invocation_root("nested")
        with pytest.raises(ValueError, match="fixture failure"), bind_kernel_invocation_root(nested):
            assert capture_kernel_invocation_root() is nested
            raise ValueError("fixture failure")
        assert capture_kernel_invocation_root() is first
    assert capture_kernel_invocation_root().root == str(tmp_path)
    if Path("C:relative").drive:
        with pytest.raises(ValueError, match="E_KERNEL_DRIVE_RELATIVE_WORKSPACE_UNSUPPORTED"):
            capture_kernel_invocation_root("C:relative")
    assert list(tmp_path.iterdir()) == []


def test_native_gateway_captures_request_before_waiting_for_runtime_lock(tmp_path):
    gateway = KernelV1Gateway(invocation_root=tmp_path)
    original = gateway.runtime.lock
    attempted = threading.Event()
    gateway.runtime.lock = ObservedKernelLock(original, attempted)
    request = {"contract_version": "kernel_api/v1", "workflow_id": "locked", "workspace_root": "first"}
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            with original:
                pending = executor.submit(gateway.start_run, request)
                assert attempted.wait(10)
                request["workspace_root"] = "later"
            assert Path(pending.result(timeout=10)["run_handle"]["workspace_root"]) == tmp_path / "first"
        assert list(tmp_path.iterdir()) == []
    finally:
        gateway.close()
