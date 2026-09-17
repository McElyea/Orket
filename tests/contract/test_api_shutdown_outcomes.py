"""Layer: contract. Synthetic owner failures test shutdown observation semantics."""
from __future__ import annotations

import asyncio

import pytest

from orket.application.services.api_runtime_container import ApiRuntimeContainer
from orket.application.services.command_process_supervisor import CommandProcessCancelled
from orket.core.contracts.owned_command import CommandExecutionUncertain, OwnedCommandResult

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


class Resource:
    def __init__(self, error=None):
        self.error, self.calls = error, 0
        self.entered, self.release = asyncio.Event(), asyncio.Event()

    async def close(self):
        self.calls += 1
        self.entered.set()
        await self.release.wait()
        if self.error is not None:
            raise self.error


def container(tmp_path, engine):
    return ApiRuntimeContainer(tmp_path, None, None, None, engine)


@pytest.mark.parametrize("error", [OSError("close failed"), asyncio.CancelledError("owner interrupted")])
# Layer: contract
async def test_failed_resource_closes_peers_and_replays_failure_to_every_caller(tmp_path, error):
    engine, peer, failure = Resource(), Resource(), Resource(error)
    engine.release.set()
    peer.release.set()
    context = container(tmp_path, engine)
    context.register_owned_resource(peer)
    context.register_owned_resource(failure)
    first = asyncio.create_task(context.close())
    await failure.entered.wait()
    second = asyncio.create_task(context.close())
    await asyncio.sleep(0)
    assert not context.closed and not context.accepting_work and not second.done()
    first.cancel()
    failure.release.set()
    with pytest.raises(RuntimeError, match="teardown failed") as observed:
        await first
    for call in (second, context.close()):
        with pytest.raises(RuntimeError) as repeated:
            await call
        assert repeated.value is observed.value and repeated.value.__cause__ is error
    assert not context.closed and not context.accepting_work
    assert engine.calls == peer.calls == failure.calls == 1


@pytest.mark.parametrize("kind", ["failure", "command_uncertain"])
# Layer: contract
async def test_background_failure_prevents_successful_shutdown_claim(tmp_path, kind):
    engine = Resource()
    engine.release.set()
    context = container(tmp_path, engine)
    entered = asyncio.Event()
    lifetime = OwnedCommandResult(None, b"", b"", "supervisor_lost", False, False,
                                  "synthetic", 1, None, None, ())

    async def background():
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            if kind == "command_uncertain":
                raise CommandProcessCancelled(lifetime) from None
            raise OSError("background teardown failed") from None

    task = asyncio.create_task(background())
    context.track_background_task(task)
    await entered.wait()
    with pytest.raises(RuntimeError, match="teardown failed") as observed:
        await context.close()
    assert isinstance(observed.value.__cause__, CommandExecutionUncertain if kind == "command_uncertain" else OSError)
    assert not context.closed and not context.accepting_work and engine.calls == 1
    assert context.active_background_task_count == 0


# Layer: contract
async def test_background_owner_cannot_deadlock_on_its_own_teardown(tmp_path):
    engine = Resource()
    engine.release.set()
    context = container(tmp_path, engine)
    go = asyncio.Event()

    async def background():
        await go.wait()
        with pytest.raises(RuntimeError, match="own teardown"):
            await context.close()

    task = asyncio.create_task(background())
    context.track_background_task(task)
    go.set()
    await asyncio.wait_for(task, 5)
    assert context.accepting_work and not context.closed
    await context.close()
    assert context.closed and engine.calls == 1


# Layer: contract
async def test_teardown_owner_cancellation_is_failure_and_still_attempts_engine(tmp_path):
    engine, resource = Resource(), Resource()
    engine.release.set()
    context = container(tmp_path, engine)
    context.register_owned_resource(resource)
    closing = asyncio.create_task(context.close())
    await resource.entered.wait()
    # Fault injection targets the owner itself, unlike cancelling a close waiter.
    context._close_task.cancel()
    with pytest.raises(RuntimeError, match="teardown failed") as observed:
        await closing
    assert isinstance(observed.value.__cause__, asyncio.CancelledError)
    assert not context.closed and not context.accepting_work and engine.calls == 1
    with pytest.raises(RuntimeError) as repeated:
        await context.close()
    assert repeated.value is observed.value


# Layer: contract
async def test_resource_cannot_recursively_await_container_teardown(tmp_path):
    engine = Resource()
    engine.release.set()
    context = container(tmp_path, engine)

    class RecursiveResource:
        async def close(self):
            await context.close()

    context.register_owned_resource(RecursiveResource())
    with pytest.raises(RuntimeError, match="teardown failed") as observed:
        await asyncio.wait_for(context.close(), 5)
    assert "own teardown" in str(observed.value.__cause__)
    assert not context.closed and engine.calls == 1
