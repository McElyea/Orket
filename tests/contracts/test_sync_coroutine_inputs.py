"""Layer: contract. Refusal retains caller ownership and disposes only unstarted inputs."""

import asyncio
import inspect

import pytest

from orket.adapters.execution.sync_coroutine_owner import SyncCoroutineOwner
from orket.capabilities.sync_bridge import run_coro_sync

pytestmark = pytest.mark.contract


def test_closed_owner_refuses_new_coroutine_and_reentry_without_running_finalizer_again():
    owner, finalized = SyncCoroutineOwner(), []

    async def finalizer():
        finalized.append("closed")

    owner.close(finalizer)
    owner.close(finalizer)
    operation = asyncio.sleep(0)
    with pytest.raises(RuntimeError, match="E_SYNC_COROUTINE_OWNER_CLOSED"):
        owner.run(operation)
    assert inspect.getcoroutinestate(operation) == inspect.CORO_CLOSED
    with pytest.raises(RuntimeError, match="E_SYNC_COROUTINE_OWNER_CLOSED"), owner:
        pytest.fail("closed owner admitted work")
    assert finalized == ["closed"] and owner.closed


@pytest.mark.parametrize("value", [None, 1, "coroutine"])
def test_non_coroutine_is_rejected(value):
    with pytest.raises(TypeError, match="expects a native coroutine"):
        run_coro_sync(value)


def test_invalid_owner_closes_only_its_unstarted_input():
    operation = asyncio.sleep(0)
    with pytest.raises(TypeError, match="E_SYNC_COROUTINE_OWNER_REQUIRED"):
        run_coro_sync(operation, owner=object())
    assert inspect.getcoroutinestate(operation) == inspect.CORO_CLOSED


def test_started_coroutine_is_refused_without_taking_its_ownership():
    operation = asyncio.sleep(0)
    operation.send(None)
    try:
        with pytest.raises(ValueError, match="E_SYNC_COROUTINE_UNSTARTED_REQUIRED"):
            run_coro_sync(operation)
        assert inspect.getcoroutinestate(operation) == inspect.CORO_SUSPENDED
    finally:
        operation.close()


def test_loop_creation_failure_disposes_coroutine_and_allows_a_fresh_attempt(monkeypatch):
    create, failure = asyncio.new_event_loop, OSError("fixture loop creation failure")
    owner = SyncCoroutineOwner()

    def failed():
        raise failure

    monkeypatch.setattr(asyncio, "new_event_loop", failed)
    operation = asyncio.sleep(0)
    with pytest.raises(OSError) as caught:
        owner.run(operation)
    assert caught.value is failure and inspect.getcoroutinestate(operation) == inspect.CORO_CLOSED
    monkeypatch.setattr(asyncio, "new_event_loop", create)
    try:
        assert owner.run(asyncio.sleep(0, result="recovered")) == "recovered"
    finally:
        owner.close()


def test_owner_cannot_close_from_its_running_coroutine():
    owner = SyncCoroutineOwner()

    async def operation():
        with pytest.raises(RuntimeError, match="E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER"):
            owner.close()
        assert owner.accepting and not owner.closed

    with owner:
        owner.run(operation())
