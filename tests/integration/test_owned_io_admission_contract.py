"""Contract: shared ownership preserves the coroutine protocol and refusal boundary."""
from __future__ import annotations

import asyncio
import inspect
import types
from collections.abc import Coroutine

import pytest

from orket.adapters.execution.owned_io import run_owned_io

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


class TaskProtocolCoroutine(Coroutine):
    """Task drives send/throw; awaiting this object is deliberately a different operation."""

    def __init__(self, coroutine):
        self.coroutine = coroutine

    def __await__(self):
        raise AssertionError("Task admission must not reinterpret the object's await protocol")

    def send(self, value):
        return self.coroutine.send(value)

    def throw(self, *args):
        return self.coroutine.throw(*args)

    def close(self):
        return self.coroutine.close()


class OtherAwaitable:
    def __init__(self):
        self.calls = 0

    def __await__(self):
        self.calls += 1
        yield
        return 17


async def native_operation(trace, failure):
    trace.append("entered")
    await asyncio.sleep(0)
    trace.append("settled")
    if failure is not None:
        raise failure
    return 17


def generator_operation(trace, failure):
    trace.append("entered")
    yield
    trace.append("settled")
    if failure is not None:
        raise failure
    return 17


@types.coroutine
def marked_generator_operation(trace, failure):
    return (yield from generator_operation(trace, failure))


def admitted_operation(kind, trace, failure):
    if kind == "native":
        return native_operation(trace, failure)
    if kind == "generator-coroutine":
        return marked_generator_operation(trace, failure)
    if kind == "task-generator":
        return generator_operation(trace, failure)
    return TaskProtocolCoroutine(native_operation(trace, failure))


@pytest.mark.parametrize("kind", ["native", "generator-coroutine", "task-generator", "abc-coroutine"])
@pytest.mark.parametrize("outcome", ["success", "exception", "cancellation"])
async def test_owned_admission_matches_direct_create_task_protocol(kind, outcome, record_property):
    failure = {"success": None, "exception": OSError("protocol failure"),
               "cancellation": asyncio.CancelledError("protocol cancellation")}[outcome]
    cause, context = LookupError("cause"), ValueError("context")
    if failure is not None:
        failure.__cause__, failure.__context__ = cause, context
    traces = []
    for owned in (False, True):
        trace = []
        operation = admitted_operation(kind, trace, failure)
        direct = None
        if not owned:
            try:
                direct = asyncio.create_task(operation)
            except TypeError as refusal:
                await assert_selected_interpreter_refusal(operation, refusal, trace)
                record_property("coroutine_admission", "selected interpreter refuses generator before execution")
                return
        try:
            result = await (run_owned_io(lambda admitted=operation: admitted, label="admission-parity")
                            if owned else direct)
        except BaseException as observed:
            assert failure is not None and observed is failure
            assert observed.__cause__ is cause and observed.__context__ is context
        else:
            assert failure is None and result == 17
        traces.append(trace)
    assert traces == [["entered", "settled"], ["entered", "settled"]]
    record_property("coroutine_admission", "selected interpreter and shared owner both execute coroutine")


async def assert_selected_interpreter_refusal(operation, refusal, trace):
    """Some supported interpreters reject both generator forms before Task execution."""
    assert inspect.isgenerator(operation)
    try:
        assert inspect.getgeneratorstate(operation) == inspect.GEN_CREATED and trace == []
        with pytest.raises(TypeError) as caught:
            await run_owned_io(lambda: operation, label="generator-admission-refusal")
        assert caught.value.args == refusal.args
        assert inspect.getgeneratorstate(operation) == inspect.GEN_CREATED and trace == []
    finally:
        operation.close()  # Both refusals leave this unstarted object with its caller.


@pytest.mark.parametrize("kind", ["future", "task", "awaitable", "value"])
async def test_refused_values_are_not_awaited_or_consumed_before_first_suspension(kind):
    loop, order = asyncio.get_running_loop(), []
    waiting = asyncio.Event()
    candidates = {"future": loop.create_future, "task": lambda: asyncio.create_task(waiting.wait()),
                  "awaitable": OtherAwaitable, "value": lambda: 17}
    candidate = candidates[kind]()
    loop.call_soon(order.append, "peer")

    def factory():
        order.append("factory")
        return candidate

    try:
        with pytest.raises(TypeError):
            await run_owned_io(factory, label="invalid-admission")
        assert order == ["factory"]
        if isinstance(candidate, (asyncio.Future, asyncio.Task)):
            assert not candidate.done() and not candidate.cancelled()
        elif isinstance(candidate, OtherAwaitable):
            assert candidate.calls == 0
    finally:
        if isinstance(candidate, (asyncio.Future, asyncio.Task)):
            candidate.cancel()
            await asyncio.gather(candidate, return_exceptions=True)


@pytest.mark.parametrize("failure", [RuntimeError("factory failure"), SystemExit(59), KeyboardInterrupt("factory stop")])
async def test_factory_failure_remains_synchronous_and_exact(failure):
    order = []
    cause, context = LookupError("factory cause"), ValueError("factory context")
    failure.__cause__, failure.__context__ = cause, context
    asyncio.get_running_loop().call_soon(order.append, "peer")

    def factory():
        order.append("factory")
        raise failure

    with pytest.raises(type(failure)) as caught:
        await run_owned_io(factory, label="factory-refusal")
    assert order == ["factory"] and caught.value is failure
    assert failure.__cause__ is cause and failure.__context__ is context


async def test_task_factory_refusal_does_not_consume_or_close_caller_owned_coroutine():
    loop, trace = asyncio.get_running_loop(), []
    operation, refusal = native_operation(trace, None), RuntimeError("task factory refused")
    previous, admitted = loop.get_task_factory(), []
    loop.call_soon(trace.append, "peer")

    def refuse(_loop, candidate, **_kwargs):
        admitted.append(candidate)
        raise refusal

    def factory():
        trace.append("factory")
        return operation

    loop.set_task_factory(refuse)
    try:
        with pytest.raises(RuntimeError) as caught:
            await run_owned_io(factory, label="task-factory-refusal")
        assert caught.value is refusal and len(admitted) == 1 and trace == ["factory"]
        assert inspect.getcoroutinestate(operation) == inspect.CORO_CREATED
    finally:
        loop.set_task_factory(previous)
        operation.close()  # The caller retains refused, unstarted work; fixture owns cleanup.


async def test_returned_base_exception_keeps_existing_failure_interpretation():
    failure = LookupError("returned failure")

    async def operation():
        return failure

    with pytest.raises(LookupError) as caught:
        await run_owned_io(operation, label="returned-failure")
    assert caught.value is failure
