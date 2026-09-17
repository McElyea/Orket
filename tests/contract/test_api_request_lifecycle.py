"""Layer: contract. Request ownership and independent cancellation observers."""
from __future__ import annotations

import asyncio

import pytest

from orket.application.services.api_runtime_container import ApiRequestAdmissionClosed
from orket.application.services.command_process_supervisor import CommandProcessCancelled
from orket.core.contracts.owned_command import CommandExecutionUncertain, OwnedCommandResult
from tests.contract.test_api_shutdown_outcomes import Resource, container

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize("kind", ["failure", "command_uncertain", "command_confirmed"])
# Layer: contract
async def test_request_and_close_both_observe_retained_cleanup_outcome(tmp_path, kind):
    engine = Resource()
    engine.release.set()
    context = container(tmp_path, engine)
    entered, stopping, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    lifetime = OwnedCommandResult(None, b"", b"", "cancelled", kind == "command_confirmed", False,
                                  "synthetic", 1, None, None, ())
    error = OSError("request cleanup failed") if kind == "failure" else CommandProcessCancelled(lifetime)

    async def request():
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            stopping.set()
            await release.wait()
            raise error from None

    caller = asyncio.create_task(context.run_request(request))
    await entered.wait()
    closing = asyncio.create_task(context.close())
    await stopping.wait()
    assert context.active_request_count == 1 and not context.closed
    for _ in range(3):
        caller.cancel()
        await asyncio.sleep(0)
    assert not caller.done() and not closing.done()
    release.set()
    with pytest.raises(type(error)) as request_error:
        await caller
    assert request_error.value is error
    if kind == "command_confirmed":
        await closing
        assert context.closed
    else:
        with pytest.raises(RuntimeError) as close_error:
            await closing
        assert isinstance(close_error.value.__cause__, OSError if kind == "failure" else CommandExecutionUncertain)
        assert not context.closed
        with pytest.raises(RuntimeError) as repeated:
            await context.close()
        assert repeated.value is close_error.value
    assert engine.calls == 1 and context.active_request_count == 0


# Layer: contract
async def test_cancelling_request_waiter_waits_for_owned_cleanup(tmp_path):
    engine = Resource()
    engine.release.set()
    context = container(tmp_path, engine)
    entered, stopping, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def request():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopping.set()
            await release.wait()

    caller = asyncio.create_task(context.run_request(request))
    await entered.wait()
    caller.cancel()
    await stopping.wait()
    for _ in range(3):
        caller.cancel()
        await asyncio.sleep(0)
    assert not caller.done() and context.active_request_count == 1
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert context.active_request_count == 0 and context.accepting_work
    await context.close()


# Layer: contract
async def test_request_descendant_cannot_await_its_own_teardown(tmp_path):
    engine = Resource()
    engine.release.set()
    context = container(tmp_path, engine)

    async def request():
        with pytest.raises(RuntimeError, match="own teardown"):
            await asyncio.create_task(context.close())

    await asyncio.wait_for(context.run_request(request), 5)
    assert context.accepting_work and context.active_request_count == 0
    await context.close()


# Layer: contract
async def test_closed_request_admission_never_constructs_invocation(tmp_path):
    engine = Resource()
    engine.release.set()
    context = container(tmp_path, engine)
    await context.close()

    def forbidden():
        pytest.fail("Closed runtime constructed request invocation")

    with pytest.raises(ApiRequestAdmissionClosed):
        await context.run_request(forbidden)
    assert context.active_request_count == 0
