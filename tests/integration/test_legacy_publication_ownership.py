"""Integration: synchronous legacy work and publication remain owned on interruption."""
from __future__ import annotations

import asyncio

import pytest

from tests.integration.test_workload_publication_inputs import admitted_legacy as admitted_legacy
from tests.integration.test_workload_publication_ownership import _hold_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("phase", ["compile", "root", "validate", "manifest-build", "manifest-write",
                                  "provenance-build", "provenance-write", "digest"])
@pytest.mark.parametrize("stop", ["cancel", "caller-timeout"])
async def test_legacy_publication_retains_worker(tmp_path, admitted_legacy, monkeypatch, phase, stop):
    manager, payload = admitted_legacy
    entered, release, settled = _hold_worker(monkeypatch, manager, phase, legacy=True)
    task = asyncio.create_task(manager.run_workload(workload_id="mystery_v1", input_config=payload,
                                                  workspace=tmp_path, department="core"))
    timeout_owner = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if stop == "cancel":
            task.cancel()
        else:
            timeout_owner = asyncio.create_task(asyncio.wait_for(task, .01))
        await asyncio.wait_for(asyncio.sleep(.03), .5)
        assert task.cancelling() == 1
        assert not task.done() and not settled.is_set()
        if stop == "cancel":
            task.cancel()
        release.set()
        with pytest.raises(TimeoutError if stop == "caller-timeout" else asyncio.CancelledError):
            await asyncio.wait_for(timeout_owner or task, 5)
        assert settled.is_set()
    finally:
        release.set()
        if entered.is_set():
            assert await asyncio.to_thread(settled.wait, 5)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, *([timeout_owner] if timeout_owner else []), return_exceptions=True)
