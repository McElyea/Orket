"""Cancellation identity and retained settlement at the shared asynchronous I/O owner."""
from __future__ import annotations

import asyncio
import threading

import pytest

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.application.services.kernel_runtime_lifetime import KernelRuntimeLifetime
from orket.application.services.kernel_runtime_owner import KernelRuntime

pytestmark = pytest.mark.asyncio
WAIT_SECONDS = 5


class _NamedCancellation(asyncio.CancelledError):
    pass


async def _wait_thread(event: threading.Event) -> None:
    assert await asyncio.wait_for(
        asyncio.to_thread(event.wait, WAIT_SECONDS), WAIT_SECONDS + 0.5)


async def _wait_task_done(task: asyncio.Task) -> None:
    done, pending = await asyncio.wait({task}, timeout=WAIT_SECONDS)
    assert done == {task} and not pending, "owned task did not settle within the fixture deadline"


@pytest.mark.integration
# Layer: integration. The real Kernel publication stack must retain its operation cancellation object.
async def test_kernel_publication_keeps_named_internal_cancellation_identity():
    runtime = KernelRuntime()
    lifetime = KernelRuntimeLifetime(runtime)
    cause = LookupError("kernel-cancellation-cause")
    context = ValueError("kernel-cancellation-context")
    cancellation = _NamedCancellation("kernel-operation-cancelled")
    cancellation.__cause__, cancellation.__context__ = cause, context

    async def operation() -> None:
        raise cancellation

    try:
        with pytest.raises(asyncio.CancelledError, match="^kernel-operation-cancelled$") as caught:
            await lifetime.invoke(operation)
        exact_cancellation = caught.value is cancellation
        exact_graph = (
            caught.value.__class__ is _NamedCancellation
            and caught.value.__cause__ is cause and caught.value.__context__ is context
        )
        assert exact_cancellation and exact_graph
        assert lifetime.active_request_count == 0
    finally:
        await lifetime.close()
    assert lifetime.closed and runtime.closed


@pytest.mark.contract
# Layer: contract. Repeated caller cancellation keeps the first request and drains admitted work.
async def test_owned_io_keeps_first_external_cancellation_through_settlement():
    entered, release, settled = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def operation() -> None:
        entered.set()
        try:
            await release.wait()
        finally:
            settled.set()

    active = asyncio.create_task(run_owned_io(operation, label="external-cancellation-control"))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        active.cancel("external-cancellation-first")
        await asyncio.sleep(0)
        assert not active.done()
        active.cancel("external-cancellation-second")
        await asyncio.sleep(0)
        assert not active.done() and not settled.is_set()
        release.set()
        await _wait_task_done(active)
        with pytest.raises(asyncio.CancelledError, match="^external-cancellation-first$"):
            active.result()
        assert settled.is_set()
    finally:
        release.set()
        if not active.done():
            active.cancel("external-cancellation-fixture-cleanup")
        await _wait_task_done(active)


@pytest.mark.integration
# Layer: integration. A retained native failure still outranks repeated caller cancellation.
async def test_owned_thread_keeps_native_failure_precedence_after_cancellation():
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    failure = OSError("owned-native-failure")

    def operation() -> None:
        entered.set()
        try:
            assert release.wait(WAIT_SECONDS), "native owner fixture was not released"
            raise failure
        finally:
            settled.set()

    active = asyncio.create_task(run_owned_thread(operation, label="native-failure-control"))
    try:
        await _wait_thread(entered)
        active.cancel("native-cancellation-first")
        await asyncio.sleep(0)
        assert not active.done()
        active.cancel("native-cancellation-second")
        await asyncio.sleep(0)
        assert not active.done() and not settled.is_set()
        release.set()
        await _wait_task_done(active)
        with pytest.raises(OSError, match="^owned-native-failure$") as caught:
            active.result()
        exact_failure = caught.value is failure
        assert exact_failure and settled.is_set()
    finally:
        release.set()
        if not active.done():
            active.cancel("native-failure-fixture-cleanup")
        await _wait_task_done(active)
        if not active.cancelled():
            active.exception()


@pytest.mark.contract
# Layer: contract. The interrupt branch cancels its child once and keeps caller scope identity.
async def test_owned_io_interrupt_cancels_child_once_and_keeps_first_caller_message():
    entered = asyncio.Event()
    child_cancelled = asyncio.Event()
    operation_release = asyncio.Event()
    cleanup_release = asyncio.Event()
    settled = asyncio.Event()
    child_cancellations: list[asyncio.CancelledError] = []

    async def operation() -> None:
        entered.set()
        try:
            await operation_release.wait()
        except asyncio.CancelledError as exc:
            child_cancellations.append(exc)
            child_cancelled.set()
            await cleanup_release.wait()
            raise
        finally:
            settled.set()

    active = asyncio.create_task(run_owned_io(
        operation, label="interrupt-cancellation-control", cancel_on_interrupt=True))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        active.cancel("interrupt-cancellation-first")
        await asyncio.wait_for(child_cancelled.wait(), 1)
        active.cancel("interrupt-cancellation-second")
        await asyncio.sleep(0)
        assert len(child_cancellations) == 1 and child_cancellations[0].args == ()
        assert not active.done() and not settled.is_set()
        cleanup_release.set()
        await _wait_task_done(active)
        with pytest.raises(asyncio.CancelledError, match="^interrupt-cancellation-first$"):
            active.result()
        assert settled.is_set() and len(child_cancellations) == 1
    finally:
        operation_release.set()
        cleanup_release.set()
        if not active.done():
            active.cancel("interrupt-cancellation-fixture-cleanup")
        await _wait_task_done(active)


@pytest.mark.contract
# Layer: contract. The shared owner retains synchronous factory timing and coroutine-only admission.
async def test_owned_io_keeps_factory_timing_and_rejects_non_coroutine_awaitables():
    order: list[str] = []
    loop = asyncio.get_running_loop()
    loop.call_soon(order.append, "peer-callback")

    def fail_before_await() -> None:
        order.append("factory")
        raise RuntimeError("factory-before-suspension")

    with pytest.raises(RuntimeError, match="^factory-before-suspension$"):
        await run_owned_io(fail_before_await, label="factory-timing-control")  # type: ignore[arg-type]
    assert order == ["factory"]
    await asyncio.sleep(0)
    assert order == ["factory", "peer-callback"]

    completed = loop.create_future()
    completed.set_result("completed-awaitable")
    with pytest.raises(TypeError):
        await run_owned_io(lambda: completed, label="coroutine-admission-control")  # type: ignore[arg-type]
    assert completed.done() and completed.result() == "completed-awaitable"
