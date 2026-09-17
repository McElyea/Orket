"""Observe teardown across an actual asyncio.run shutdown in another interpreter."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import psutil
import pytest

from tests.integration.test_verification_process_lifetime import (
    assert_stopped,
    await_fixture_bootstrap,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("caller", ["verification", "outward-command"])
# Layer: integration
async def test_event_loop_shutdown_confirms_descendants_before_interpreter_exit(tmp_path, caller):
    worker = Path(__file__).with_name("verification_shutdown_worker.py")
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(worker), str(tmp_path), caller,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    output = asyncio.create_task(process.communicate())
    processes = []
    try:
        await await_fixture_bootstrap(tmp_path, process, output)
        processes = await await_tree(tmp_path)
        await asyncio.to_thread((tmp_path / "shutdown-now").touch)
        stdout, stderr = await asyncio.wait_for(asyncio.shield(output), 10)
        assert process.returncode == 0, stderr.decode("utf-8", errors="replace")
        events = [json.loads(line) for line in stdout.splitlines()]
        event_name = "verification_process_cancelled" if caller == "verification" else "outward_command_cancelled"
        lifetime = [e["data"] for e in events if e["event"] == event_name]
        assert len(lifetime) == 1, (stdout, stderr)
        assert lifetime[0]["cleanup_confirmed"] is True, lifetime
        assert not await asyncio.to_thread(psutil.pid_exists, lifetime[0]["supervisor_pid"])
        assert not await asyncio.to_thread(psutil.pid_exists, lifetime[0]["transport_pid"])
        await assert_stopped(processes, tmp_path)
    finally:
        if not processes:
            processes = await asyncio.to_thread(observe_processes, tmp_path)
        await asyncio.to_thread(stop_observed, processes)
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(output, 5)
