"""Layer: integration. Observe real trees through standard sandbox composition."""
from __future__ import annotations

import asyncio
import sys
from functools import partial

import psutil
import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from tests.integration.test_verification_process_lifetime import (
    WORKER,
    assert_stopped,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def standard_runner(root):
    orchestrator = await run_owned_thread(partial(
        SandboxOrchestrator, workspace_root=root, lifecycle_db_path=str(root / "lifecycle.db")),
        label="sandbox-command-test-construction")
    return orchestrator.command_runner


@pytest.mark.parametrize("stop", ["cancel", "repeated-cancel", "admitted-timeout", "leader-exit", "leader-failure"])
@pytest.mark.parametrize("flags", [[], ["detached", "ignore-term"]], ids=["ordinary", "detached-resistant"])
async def test_standard_sandbox_runner_owns_process_tree(tmp_path, stop, flags, caplog):
    runner = await standard_runner(tmp_path)
    task = asyncio.create_task(runner.run_async(sys.executable, str(WORKER), str(tmp_path), "2", *flags, stop))
    processes = []
    try:
        processes = await await_tree(tmp_path)
        if stop == "admitted-timeout":
            with pytest.raises(TimeoutError):
                async with asyncio.timeout(0.05):
                    await task
        elif stop in {"cancel", "repeated-cancel"}:
            task.cancel()
            if stop == "repeated-cancel":
                for _ in range(20):
                    if task.done():
                        break
                    await asyncio.sleep(0.01)
                    task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
        else:
            await asyncio.to_thread((tmp_path / "release-leader").touch)
            result = await asyncio.wait_for(asyncio.shield(task), 5)
            assert result.returncode == (7 if stop == "leader-failure" else 0)
        await assert_stopped(processes, tmp_path)
        if stop in {"leader-exit", "leader-failure"}:
            lifetime = result.lifetime.lifetime()
        else:
            lifetime, = [row.orket_record["data"] for row in caplog.records
                         if row.message == "sandbox_command_interrupted"]
        assert lifetime["cleanup_confirmed"] is True and lifetime["capture_complete"] is True
        assert lifetime["backend"] == ("windows_job" if sys.platform == "win32" else "linux_subreaper")
        for key in ("supervisor_pid", "transport_pid"):
            assert not await asyncio.to_thread(psutil.pid_exists, lifetime[key])
    finally:
        if not processes:
            processes = await asyncio.to_thread(observe_processes, tmp_path)
        await asyncio.to_thread(stop_observed, processes)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await assert_stopped(processes, tmp_path)
