"""Layer: integration. Real Kernel and SQLite effects remain owned through teardown."""

import asyncio
import threading
from functools import partial

import aiosqlite
import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.kernel_invocation_service import invoke_kernel
from orket.application.services.kernel_runtime_lifetime import KernelRuntimeLifetime
from orket.application.services.kernel_runtime_owner import KernelRuntime, current_kernel_runtime
from orket.application.services.kernel_v1_gateway import KernelV1Gateway
from orket.core.domain import ReservationStatus
from orket.kernel.v1.nervous_system_runtime import admit_proposal_v1
from tests.helpers.kernel_state_probe import kernel_app, responsive_sqlite
from tests.integration.test_kernel_publication_input_capture import hold_first_lookup
from tests.integration.test_kernel_runtime_isolation import kernel_enabled as kernel_enabled
from tests.integration.test_kernel_runtime_isolation import request

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("kernel_enabled")]


async def test_native_gateway_refuses_event_loop_before_state_effects():
    gateway = KernelV1Gateway()
    try:
        with pytest.raises(RuntimeError, match="E_KERNEL_INVOCATION_REQUIRES_ASYNC_OWNER"):
            gateway.admit_proposal(request())
        assert gateway.runtime.ledger_by_session == {}
        result = await invoke_kernel(gateway.admit_proposal, request())
        assert result["admission_decision"]["decision"] == "ACCEPT_TO_UNIFY"
    finally:
        await run_owned_thread(gateway.close, label="gateway-close")
    assert gateway.runtime.closed


async def test_direct_open_closes_on_error_and_refuses_sync_close_on_event_loop():
    with pytest.raises(ValueError, match="fixture abort"):
        async with KernelRuntime.open() as owner:
            assert current_kernel_runtime() is owner
            with pytest.raises(RuntimeError, match="E_KERNEL_CLOSE_REQUIRES_ASYNC_OWNER"):
                owner.close()
            assert not owner.closed
            await invoke_kernel(admit_proposal_v1, request())
            raise ValueError("fixture abort")
    assert owner.closed and len(owner.ledger_by_session["same-session"]) == 2
    with pytest.raises(RuntimeError, match="E_KERNEL_RUNTIME_OWNER_REQUIRED"):
        current_kernel_runtime()


async def test_native_close_waits_for_owned_lock_without_blocking_other_owners(tmp_path, record_property):
    left, right = KernelRuntime(), KernelRuntime()
    lifetime = KernelRuntimeLifetime(left)
    entered, release = threading.Event(), threading.Event()

    def held_transition():
        with left.activate(), left.lock:
            result = admit_proposal_v1(request())
            entered.set()
            assert release.wait(10), "native Kernel close fixture was not released"
            return result

    active = asyncio.create_task(run_owned_thread(held_transition, label="native-kernel-transition"))
    closing = None
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 10), 10)
        closing = asyncio.create_task(lifetime.close())
        await asyncio.sleep(0.03)
        closing.cancel()
        await asyncio.sleep(0)
        closing.cancel()
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        assert not closing.done() and not left.closed
        with right.activate():
            result = await asyncio.wait_for(invoke_kernel(admit_proposal_v1, request()), 0.5)
            assert result["admission_decision"]["decision"] == "ACCEPT_TO_UNIFY"
        release.set()
        assert (await asyncio.wait_for(active, 10))["proposal_digest"] == result["proposal_digest"]
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(closing, 10)
        await lifetime.close()
        assert lifetime.closed and left.closed and not right.closed
        with pytest.raises(RuntimeError, match="closing"):
            await lifetime.invoke(partial(invoke_kernel, admit_proposal_v1, request()))
    finally:
        release.set()
        await asyncio.gather(active, *([closing] if closing else []), return_exceptions=True)
        await lifetime.close()
        await run_owned_thread(right.close, label="right-kernel-close")


async def test_engine_close_keeps_nested_approval_publication_and_rejects_late_admission(tmp_path, monkeypatch):
    app = kernel_app(tmp_path)
    async with app.router.lifespan_context(app):
        engine = app.state.api_runtime_context.engine
        entered, release = hold_first_lookup(monkeypatch, engine.control_plane_execution_repository)
        active = asyncio.create_task(engine.kernel_admit_proposal_async(request(approval_required_credentialed=True)))
        closing = None
        try:
            await asyncio.wait_for(entered.wait(), 10)
            closing = asyncio.create_task(engine.close())
            await asyncio.sleep(0.03)
            with pytest.raises(RuntimeError, match="closing"):
                await engine.kernel_admit_proposal_async({**request(), "session_id": "too-late"})
            closing.cancel()
            await asyncio.sleep(0)
            closing.cancel()
            await asyncio.sleep(0.03)
            assert not closing.done() and not active.done()
            release.set()
            outcomes = await asyncio.wait_for(asyncio.gather(active, closing, return_exceptions=True), 10)
            assert isinstance(outcomes[0], (dict, asyncio.CancelledError))
            assert isinstance(outcomes[1], asyncio.CancelledError)
            await engine.close()
            assert engine._closed and engine.kernel_gateway.runtime.closed
            runtime = engine.kernel_gateway.runtime
            assert "too-late" not in runtime.ledger_by_session
            (approval,) = runtime.approvals_by_id.values()
            reservation = await engine.control_plane_repository.get_latest_reservation_record(
                reservation_id="approval-reservation:" + approval["approval_id"]
            )
            assert reservation is not None and reservation.status is ReservationStatus.ACTIVE
        finally:
            release.set()
            await asyncio.gather(active, *([closing] if closing else []), return_exceptions=True)


async def test_sqlite_failure_during_close_is_retained_for_request_and_repeated_close(tmp_path):
    owner = KernelRuntime()
    lifetime = KernelRuntimeLifetime(owner)
    entered, release = asyncio.Event(), asyncio.Event()

    async def publish():
        await invoke_kernel(admit_proposal_v1, request())
        entered.set()
        await release.wait()
        async with aiosqlite.connect(tmp_path / "actual-failure.sqlite3") as connection:
            await connection.execute("SELECT * FROM absent_kernel_publication")

    active = asyncio.create_task(lifetime.invoke(publish))
    closing = None
    try:
        await asyncio.wait_for(entered.wait(), 10)
        closing = asyncio.create_task(lifetime.close())
        await asyncio.sleep(0.03)
        closing.cancel()
        await asyncio.sleep(0)
        closing.cancel()
        assert not closing.done()
        release.set()
        outcomes = await asyncio.wait_for(asyncio.gather(active, closing, return_exceptions=True), 10)
        assert isinstance(outcomes[0], aiosqlite.OperationalError)
        assert isinstance(outcomes[1], RuntimeError)
        assert outcomes[1].__cause__ is outcomes[0]
        with pytest.raises(RuntimeError) as repeated:
            await lifetime.close()
        assert repeated.value is outcomes[1]
        assert owner.closed and not lifetime.closed
        assert len(owner.ledger_by_session["same-session"]) == 2
    finally:
        release.set()
        await asyncio.gather(active, *([closing] if closing else []), return_exceptions=True)
        await run_owned_thread(owner.close, label="failed-kernel-owner-close")


async def test_inherited_context_cannot_admit_new_child_after_close_but_owned_continuation_finishes():
    owner = KernelRuntime()
    lifetime = KernelRuntimeLifetime(owner)
    entered, release = asyncio.Event(), asyncio.Event()

    async def publish():
        entered.set()
        await release.wait()
        with pytest.raises(RuntimeError, match="closing"):
            await asyncio.create_task(lifetime.invoke(partial(invoke_kernel, admit_proposal_v1, request())))
        return await lifetime.invoke(partial(invoke_kernel, admit_proposal_v1, request()))

    active = asyncio.create_task(lifetime.invoke(publish))
    closing = None
    try:
        await asyncio.wait_for(entered.wait(), 10)
        closing = asyncio.create_task(lifetime.close())
        await asyncio.sleep(0.03)
        release.set()
        outcomes = await asyncio.wait_for(asyncio.gather(active, closing, return_exceptions=True), 10)
        assert isinstance(outcomes[0], (dict, asyncio.CancelledError)) and outcomes[1] is None
        assert owner.closed and lifetime.closed
        assert len(owner.ledger_by_session["same-session"]) == 2
    finally:
        release.set()
        await asyncio.gather(active, *([closing] if closing else []), return_exceptions=True)
        await lifetime.close()


async def test_owned_publication_refuses_to_await_its_own_teardown():
    owner = KernelRuntime()
    lifetime = KernelRuntimeLifetime(owner)

    async def publish():
        await invoke_kernel(admit_proposal_v1, request())
        with pytest.raises(RuntimeError, match="own teardown"):
            await lifetime.close()

    try:
        await asyncio.wait_for(lifetime.invoke(publish), 10)
        assert not owner.closed and lifetime.accepting_work
    finally:
        await lifetime.close()
