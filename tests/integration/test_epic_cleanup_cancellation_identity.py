"""Integration: epic journal cleanup distinguishes native cancellation from caller interruption."""
from __future__ import annotations

import asyncio

import pytest

from tests.helpers.governed_read_ownership import interrupt_held_read
from tests.helpers.outward_store_ownership import NativeStoreProbe
from tests.helpers.runtime_verification_hold import wait_entered
from tests.integration.test_epic_admission_native_ownership import inputs

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("phase,body_fails", [("rollback", True), ("close", True), ("close", False)])
@pytest.mark.parametrize("native_cancels", [False, True])
@pytest.mark.parametrize("mode", ["none", "cancel", "timeout"])
async def test_epic_cleanup_selects_native_failure_without_losing_body_or_commit_truth(
    tmp_path, monkeypatch, record_property, phase, body_fails, native_cancels, mode,
):
    repository, service, request, binding = inputs(tmp_path)
    admission = await service.claim("seed", request, binding)
    updated = admission.model_copy(update={"initialization_started": True})
    body_failure = ValueError("application publication body failed")
    native_failure = asyncio.CancelledError("native epic cleanup acknowledgement cancelled")
    probe = NativeStoreProbe(monkeypatch, repository.db_path, phase,
        failure=native_failure if native_cancels else None)
    caller = []

    async def publish():
        caller.append(asyncio.current_task())
        async with repository.transaction("seed") as transaction:
            assert asyncio.current_task() is caller[0]
            await transaction.save_admission(updated)
            if body_fails:
                raise body_failure

    task = asyncio.create_task(publish())
    waiter = task
    try:
        if mode == "none":
            await wait_entered(probe)
        else:
            waiter = await interrupt_held_read(task, probe, mode, tmp_path / "sibling.sqlite3", record_property)
        probe.release.set()
        if native_cancels:
            with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError) as observed:
                await waiter
            retained = observed.value.__cause__ if mode == "timeout" else observed.value
            assert retained is native_failure
            if body_fails:
                assert retained.__context__ is body_failure
        elif body_fails:
            with pytest.raises(ValueError) as observed:
                await waiter
            assert observed.value is body_failure
        elif mode != "none":
            with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
                await waiter
        else:
            assert await waiter is None
        await probe.assert_settled()
        async with repository.transaction("seed") as transaction:
            assert await transaction.get_admission() == (admission if body_fails else updated)
        await probe.assert_settled()
    finally:
        await probe.cleanup(task, waiter)
