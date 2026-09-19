"""Integration: retain real SDK exchange workers and their native execution."""
from __future__ import annotations

import asyncio
import json
import tempfile
import threading

import pytest

from orket.adapters.storage.sdk_workload_exchange import SdkWorkloadExchange
from orket.extensions.sdk_workload_runner import SdkSubprocessExecutionUncertain, run_sdk_workload_in_subprocess
from tests.helpers.sdk_lifetime import sdk_request

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("method", ["prepare", "read_result", "remove"])
@pytest.mark.parametrize("stop", ["cancel", "caller-timeout"])
async def test_sdk_keeps_exchange_worker_until_settlement(tmp_path, monkeypatch, method, stop):
    exchanges = tmp_path / "exchanges"
    exchanges.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(exchanges))
    entered, release = threading.Event(), threading.Event()
    original = getattr(SdkWorkloadExchange, method)
    observed = {}

    def held(owner, *args):
        result = original(owner, *args) if method != "remove" else None
        observed["root"] = owner.root
        observed["request"] = json.loads((owner.root / "request.json").read_bytes())
        entered.set()
        if not release.wait(10):
            raise RuntimeError("held SDK worker was never released")
        return original(owner, *args) if method == "remove" else result

    monkeypatch.setattr(SdkWorkloadExchange, method, held)
    options = sdk_request(tmp_path)
    options["input_payload"]["nested"] = {"value": "captured"}
    task = asyncio.create_task(run_sdk_workload_in_subprocess(**options))
    timeout_owner = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        options["input_payload"]["nested"]["value"] = "changed after admission"
        if stop == "cancel":
            task.cancel()
        else:
            timeout_owner = asyncio.create_task(asyncio.wait_for(task, .01))
        # Observe a loop timer while the real worker is held; the cancellation
        # count below, not elapsed time, establishes that interruption arrived.
        await asyncio.wait_for(asyncio.sleep(.03), .5)
        assert task.cancelling() == 1
        assert not task.done() and observed["root"].is_dir()
        assert observed["request"]["input_payload"]["nested"] == {"value": "captured"}
        if stop == "cancel":
            task.cancel()
        release.set()
        with pytest.raises(TimeoutError if stop == "caller-timeout" else asyncio.CancelledError):
            await asyncio.wait_for(timeout_owner or task, 5)
        assert task.cancelled()
        assert not observed["root"].exists()
        assert (tmp_path / "sdk-effect").exists() is (method != "prepare")
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, *([timeout_owner] if timeout_owner else []), return_exceptions=True)


@pytest.mark.parametrize("method", ["read_result", "remove"])
async def test_post_dispatch_exchange_failure_keeps_observation_and_files(tmp_path, monkeypatch, method):
    exchanges = tmp_path / "exchanges"
    exchanges.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(exchanges))

    def fail(_owner):
        raise PermissionError("controlled exchange refusal")

    monkeypatch.setattr(SdkWorkloadExchange, method, fail)
    with pytest.raises(SdkSubprocessExecutionUncertain) as caught:
        await asyncio.wait_for(run_sdk_workload_in_subprocess(**sdk_request(tmp_path)), 10)
    assert caught.value.phase == ("result-read" if method == "read_result" else "exchange-remove")
    assert caught.value.lifetime.cleanup_confirmed
    assert caught.value.exchange_path.is_dir()
    assert isinstance(caught.value.__cause__, PermissionError)
    assert (tmp_path / "sdk-effect").read_text() == "executed"
