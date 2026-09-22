"""Layer: integration. Native inventory and governance commands retain actual descendant trees."""
import asyncio
import sys

import psutil
import pytest

from orket.application.services.command_process_supervisor import CommandProcessCancelled, CommandProcessSupervisor
from orket.runtime.config import provider_runtime_inventory as inventory
from orket.runtime.config.provider_runtime_target import _owned_inventory
from scripts.governance import record_truthful_runtime_packet1_live_proof as packet1
from tests.integration.test_verification_process_lifetime import (
    WORKER,
    assert_stopped,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def command_receipts(monkeypatch):
    original, receipts = CommandProcessSupervisor.run, []

    async def observe(owner, *args, **kwargs):
        try:
            result = await original(owner, *args, **kwargs)
        except CommandProcessCancelled as exc:
            receipts.append(exc.lifetime)
            raise
        receipts.append(result)
        return result

    monkeypatch.setattr(CommandProcessSupervisor, "run", observe)
    return receipts


async def _assert_receipt(receipts):
    result, = receipts
    assert result.cleanup_confirmed and result.capture_complete
    assert result.backend == ("windows_job" if sys.platform == "win32" else "linux_subreaper")
    for pid in (result.supervisor_pid, result.transport_pid):
        assert not await asyncio.to_thread(psutil.pid_exists, pid)
    return result


async def _cleanup_fixture(task, processes, root):
    if not processes:
        processes = await asyncio.to_thread(observe_processes, root)
    await asyncio.to_thread(stop_observed, processes)
    if not task.done():
        task.cancel()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    await assert_stopped(processes, root)


@pytest.mark.parametrize("route", ["inventory", "packet1"])
@pytest.mark.parametrize("flags", [[], ["detached", "ignore-term"]], ids=["ordinary", "detached-resistant"])
async def test_command_leader_exit_settles_descendants_before_return(tmp_path, monkeypatch, command_receipts, route, flags):
    monkeypatch.chdir(tmp_path)
    command = [sys.executable, str(WORKER), str(tmp_path), "2", *flags, "leader-exit"]
    operation = (_owned_inventory(inventory._run_command_sync, cmd=command, timeout_s=10)
                 if route == "inventory" else packet1._run_command(*command))
    task = asyncio.create_task(operation)
    processes = []
    try:
        processes = await await_tree(tmp_path)
        await asyncio.to_thread((tmp_path / "release-leader").touch)
        result = await asyncio.wait_for(asyncio.shield(task), 5)
        assert result == ("" if route == "inventory" else (0, "", ""))
        await assert_stopped(processes, tmp_path)
        assert (await _assert_receipt(command_receipts)).returncode == 0
    finally:
        await _cleanup_fixture(task, processes, tmp_path)


@pytest.mark.parametrize("repeat", [False, True], ids=["cancel", "repeated-cancel"])
@pytest.mark.parametrize("flags", [[], ["detached", "ignore-term"]], ids=["ordinary", "detached-resistant"])
async def test_packet1_command_cancellation_retains_descendants(tmp_path, monkeypatch, command_receipts, repeat, flags):
    monkeypatch.chdir(tmp_path)
    task = asyncio.create_task(packet1._run_command(sys.executable, str(WORKER), str(tmp_path), "2", *flags))
    processes = []
    try:
        processes = await await_tree(tmp_path)
        task.cancel()
        if repeat:
            for _ in range(20):
                if task.done():
                    break
                await asyncio.sleep(.01)
                task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 5)
        await assert_stopped(processes, tmp_path)
        assert (await _assert_receipt(command_receipts)).reason == "cancelled"
    finally:
        await _cleanup_fixture(task, processes, tmp_path)


@pytest.mark.parametrize("route", ["inventory", "packet1"])
@pytest.mark.parametrize("stop", ["timeout", "leader-failure"])
@pytest.mark.parametrize("flags", [[], ["detached", "ignore-term"]], ids=["ordinary", "detached-resistant"])
async def test_command_failure_settles_observed_tree(tmp_path, monkeypatch, command_receipts, route, stop, flags):
    monkeypatch.chdir(tmp_path)
    command = [sys.executable, str(WORKER), str(tmp_path), "2", *flags, stop]
    # Keep the established five-second command budget separate from fixture admission.
    operation = (_owned_inventory(inventory._run_command_sync, cmd=command, timeout_s=5)
                 if route == "inventory" else packet1._run_command(*command, timeout_seconds=5))
    task = asyncio.create_task(operation)
    processes = []
    try:
        processes = await await_tree(tmp_path)
        if stop == "leader-failure":
            await asyncio.to_thread((tmp_path / "release-leader").touch)
        if route == "inventory":
            with pytest.raises(inventory.ProviderRuntimeWarmupError, match="timeout" if stop == "timeout" else "exit=7"):
                await asyncio.wait_for(asyncio.shield(task), 10)
        elif stop == "timeout":
            with pytest.raises(RuntimeError, match="E_PACKET1_COMMAND_INCOMPLETE:timeout"):
                await asyncio.wait_for(asyncio.shield(task), 10)
        else:
            assert await asyncio.wait_for(asyncio.shield(task), 5) == (7, "", "")
        await assert_stopped(processes, tmp_path)
        result = await _assert_receipt(command_receipts)
        assert result.reason == ("timeout" if stop == "timeout" else "completed")
        if stop == "leader-failure":
            assert result.returncode == 7
    finally:
        await _cleanup_fixture(task, processes, tmp_path)


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_inventory_waiter_retains_native_deadline_and_failure(tmp_path, monkeypatch, command_receipts, stop):
    monkeypatch.chdir(tmp_path)
    command = [sys.executable, str(WORKER), str(tmp_path), "2", "detached", "ignore-term"]

    async def invoke():
        async with asyncio.timeout(None) as deadline:
            deadlines.append(deadline)
            return await _owned_inventory(inventory._run_command_sync, cmd=command, timeout_s=5)

    deadlines, processes = [], []
    task = asyncio.create_task(invoke())
    try:
        processes = await await_tree(tmp_path)
        if stop == "timeout":
            deadlines[0].reschedule(asyncio.get_running_loop().time() + .05)
        else:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.08)
        assert not task.done()
        # The admitted native command fails at its own deadline; worker failure wins.
        with pytest.raises(inventory.ProviderRuntimeWarmupError, match="timeout"):
            await asyncio.wait_for(asyncio.shield(task), 10)
        await assert_stopped(processes, tmp_path)
        assert (await _assert_receipt(command_receipts)).reason == "timeout"
    finally:
        await _cleanup_fixture(task, processes, tmp_path)
