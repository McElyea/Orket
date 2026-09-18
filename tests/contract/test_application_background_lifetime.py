"""Layer: contract. Observe retained background failures and pre-start resource ownership."""

from __future__ import annotations

import asyncio

import pytest

from orket.application.services.application_runtime_lifetime import (
    ApplicationRuntimeLifetime,
    RequestAdmissionClosed,
)

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


class Owner(ApplicationRuntimeLifetime):
    async def _close_final_resource(self):
        self.final_closed = True


class Resource:
    def __init__(self):
        self.closes = 0

    async def close(self):
        self.closes += 1


async def test_completed_background_failure_closes_admission_and_prevents_clean_close():
    owner = Owner()
    failure = OSError("review failed")

    async def invoke():
        raise failure

    task = owner.start_background(invoke)
    await task
    assert not owner.accepting_work
    with pytest.raises(RequestAdmissionClosed):
        owner.start_background(invoke)
    with pytest.raises(RuntimeError, match="teardown failed") as first:
        await owner.close()
    with pytest.raises(RuntimeError) as second:
        await owner.close()
    assert first.value is second.value and first.value.__cause__ is failure
    assert owner.final_closed and not owner.closed and owner.active_background_task_count == 0


async def test_cancelled_before_start_keeps_constructed_resource_owned_by_parent():
    owner, resource = Owner(), Resource()
    owner.register_owned_resource(resource)
    invoked = False

    async def invoke():
        nonlocal invoked
        invoked = True
        try:
            owner.release_owned_resource(resource)
        finally:
            await resource.close()

    task = owner.start_background(invoke)
    task.cancel()
    await owner.close()
    assert not invoked and owner.closed and resource.closes == 1


async def test_registered_completed_failure_is_observed_at_teardown():
    owner = Owner()
    failure = OSError("registered task failed")

    async def invoke():
        raise failure

    task = asyncio.create_task(invoke())
    owner.track_background_task(task)
    await asyncio.gather(task, return_exceptions=True)
    with pytest.raises(RuntimeError) as observed:
        await owner.close()
    assert observed.value.__cause__ is failure and owner.final_closed and not owner.closed


async def test_background_descendant_cannot_await_its_own_owner_teardown():
    owner = Owner()

    async def descendant():
        with pytest.raises(RuntimeError, match="own teardown"):
            await owner.close()

    async def invoke():
        await asyncio.create_task(descendant())

    await asyncio.wait_for(owner.start_background(invoke), 5)
    await owner.close()
    assert owner.closed


async def test_started_background_owns_transferred_resource_through_close():
    owner, resource = Owner(), Resource()
    entered, cleanup, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    owner.register_owned_resource(resource)

    async def invoke():
        try:
            owner.release_owned_resource(resource)
            entered.set()
            await asyncio.Event().wait()
        finally:
            cleanup.set()
            await release.wait()
            await resource.close()

    owner.start_background(invoke)
    await entered.wait()
    closing = asyncio.create_task(owner.close())
    await cleanup.wait()
    closing.cancel()
    await asyncio.sleep(0)
    closing.cancel()
    assert not closing.done() and not owner.closed and resource.closes == 0
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await closing
    assert owner.closed and resource.closes == 1 and owner.active_background_task_count == 0
