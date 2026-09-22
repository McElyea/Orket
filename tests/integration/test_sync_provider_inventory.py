"""Layer: integration. Native inventory helpers share owned loops and refuse async blocking."""

import asyncio
import inspect
import sys

import pytest

from orket.runtime.config import provider_runtime_inventory as inventory

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_inventory_coroutine_refusal_closes_unstarted_input():
    operation = asyncio.sleep(0)
    try:
        with pytest.raises(RuntimeError) as caught:
            inventory._run_coro_sync(operation)
        assert inspect.getcoroutinestate(operation) == inspect.CORO_CLOSED
        assert str(caught.value) == "E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER"
    finally:
        operation.close()


@pytest.mark.asyncio
async def test_inventory_native_command_refuses_loop_before_file_effect(tmp_path):
    path = tmp_path / "inventory-effect"
    command = [
        sys.executable,
        "-c",
        "from pathlib import Path; import sys; Path(sys.argv[1]).write_bytes(b'observed')",
        str(path),
    ]
    with pytest.raises(RuntimeError, match="E_PROVIDER_INVENTORY_REQUIRES_ASYNC_OWNER"):
        inventory._run_command_sync(command, timeout_s=5)
    assert not await asyncio.to_thread(path.exists)
    assert await asyncio.to_thread(inventory._run_command_sync, command, timeout_s=5) == ""
    assert await asyncio.to_thread(path.read_bytes) == b"observed"


def test_inventory_operation_closes_its_loop():
    async def observe():
        return asyncio.get_running_loop()

    loop = inventory._run_coro_sync(observe())
    assert loop.is_closed()
