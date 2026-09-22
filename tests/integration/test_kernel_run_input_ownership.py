"""Layer: integration. Selected identity callbacks retain real lifecycle effects."""

import asyncio
import threading
from functools import partial

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.kernel_invocation_service import invoke_kernel
from orket.application.services.kernel_runtime_lifetime import KernelRuntimeLifetime
from orket.application.services.kernel_v1_gateway import KernelV1Gateway
from tests.helpers.kernel_capability_probe import turn_request
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_kernel_run_capture import SelectedInputs

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("interruption", ["cancel", "timeout", "failure"])
async def test_selected_identity_stays_owned_through_shutdown(tmp_path, record_property, interruption):
    entered, release = threading.Event(), threading.Event()
    failure = OSError("selected identity failed after admission")
    threads = []

    def selected():
        threads.append(threading.get_ident())
        entered.set()
        assert release.wait(10), "identity callback was not released"
        if interruption == "failure":
            raise failure
        return "run-selected-owned"

    source = SelectedInputs(selected)
    gateway = KernelV1Gateway(runtime_inputs=source, invocation_root=tmp_path)
    lifetime = KernelRuntimeLifetime(gateway.runtime)
    operation = partial(
        invoke_kernel, gateway.run_lifecycle, workflow_id="ownership", execute_turn_requests=[turn_request("unused")]
    )
    active = asyncio.create_task(lifetime.invoke(operation))
    closing = waiter = None
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 10), 10)
        assert threads == [threads[0]] and threads[0] != threading.get_ident()
        closing = asyncio.create_task(lifetime.close())
        if interruption == "timeout":
            waiter = asyncio.create_task(asyncio.wait_for(active, 0.02))
        else:
            active.cancel()
            await asyncio.sleep(0)
            active.cancel()
        await asyncio.sleep(0.04)
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        assert not active.done() and not closing.done() and not gateway.runtime.closed
        release.set()
        outcomes = await asyncio.wait_for(
            asyncio.gather(active, closing, *([waiter] if waiter else []), return_exceptions=True), 10
        )
        if interruption == "failure":
            assert outcomes[0] is failure
            assert isinstance(outcomes[1], RuntimeError) and outcomes[1].__cause__ is failure
            assert not await asyncio.to_thread((tmp_path / ".orket_kernel").exists)
        else:
            assert isinstance(outcomes[0], asyncio.CancelledError) and outcomes[1] is None
            if waiter:
                assert isinstance(outcomes[2], TimeoutError)
            assert await asyncio.to_thread(lambda: bool(list((tmp_path / ".orket_kernel").rglob("fixture.json"))))
        assert gateway.runtime.closed and source.calls == 1
    finally:
        release.set()
        await asyncio.gather(
            active, *([closing] if closing else []), *([waiter] if waiter else []), return_exceptions=True
        )
        await run_owned_thread(gateway.close, label="identity-fixture-close")


async def test_concurrent_owners_keep_separate_selected_ids_and_roots(tmp_path):
    left = KernelV1Gateway(runtime_inputs=SelectedInputs(lambda: "run-left"), invocation_root=tmp_path / "left")
    right = KernelV1Gateway(runtime_inputs=SelectedInputs(lambda: "run-right"), invocation_root=tmp_path / "right")
    try:
        values = await asyncio.gather(
            *[
                invoke_kernel(
                    gateway.run_lifecycle, workflow_id="concurrent", execute_turn_requests=[turn_request("unused")]
                )
                for gateway in (left, right)
            ]
        )
        for name, value in zip(("left", "right"), values, strict=True):
            assert value["start"]["run_handle"]["run_id"] == "run-" + name
            assert value["start"]["run_handle"]["workspace_root"] == str(tmp_path / name / ".orket_kernel")
            assert value["turns"][0]["outcome"] == "PASS"
            assert await asyncio.to_thread(lambda root=tmp_path / name: bool(list(root.rglob("fixture.json"))))
    finally:
        await asyncio.gather(
            *[run_owned_thread(gateway.close, label="concurrent-kernel-close") for gateway in (left, right)]
        )
    assert left.runtime.closed and right.runtime.closed
