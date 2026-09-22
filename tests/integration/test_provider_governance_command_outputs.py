"""Layer: integration. Preserve actual CLI output, native refusal and captured process inputs."""
import asyncio
import json
import sys
import threading

import psutil
import pytest

from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.core.contracts.owned_command import CommandExecutionUncertain
from orket.runtime.config import provider_runtime_inventory as inventory
from orket.runtime.config.provider_runtime_target import _owned_inventory
from scripts.governance import record_truthful_runtime_packet1_live_proof as packet1

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("route", ["inventory", "packet1"])
async def test_command_output_keeps_existing_decoding(tmp_path, monkeypatch, route):
    monkeypatch.chdir(tmp_path)
    command = [sys.executable, "-c", "import os; os.write(1,b'first\\r\\nsecond\\rlast\\xff'); os.write(2,b'err\\r\\n')"]
    if route == "inventory":
        assert await _owned_inventory(inventory._run_command_sync, cmd=command, timeout_s=5) == "first\nsecond\nlast\ufffd"
    else:
        assert await packet1._run_command(*command) == (0, "first\r\nsecond\rlast\ufffd", "err\r\n")


@pytest.mark.parametrize("route", ["inventory", "packet1"])
async def test_missing_command_does_not_return_normal_output(tmp_path, monkeypatch, route):
    monkeypatch.chdir(tmp_path)
    command = [str(tmp_path / "missing-cli.exe")]
    if route == "inventory":
        with pytest.raises(inventory.ProviderRuntimeWarmupError, match="launch_failed"):
            await _owned_inventory(inventory._run_command_sync, cmd=command, timeout_s=5)
    else:
        with pytest.raises(RuntimeError, match="E_PACKET1_COMMAND_INCOMPLETE:launch_failed"):
            await packet1._run_command(*command)


@pytest.mark.parametrize("route", ["inventory", "packet1"])
async def test_admitted_command_uses_captured_cwd_and_environment(tmp_path, monkeypatch, route):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_COMMAND_INPUT_FIXTURE", "captured")
    original = CommandProcessSupervisor.run
    entered, release = asyncio.Event(), threading.Event()
    loop = asyncio.get_running_loop()
    changed = tmp_path / "changed"
    await asyncio.to_thread(changed.mkdir)

    async def held(owner, *args, **kwargs):
        loop.call_soon_threadsafe(entered.set)
        # Inventory runs on its native owner's loop; wait through a shared thread-safe event.
        assert await asyncio.to_thread(release.wait, 5)
        return await original(owner, *args, **kwargs)

    monkeypatch.setattr(CommandProcessSupervisor, "run", held)
    script = "import os,json; print(json.dumps([os.getcwd(),os.environ['ORKET_COMMAND_INPUT_FIXTURE']]))"
    command = [sys.executable, "-c", script]
    operation = (_owned_inventory(inventory._run_command_sync, cmd=command, timeout_s=5)
                 if route == "inventory" else packet1._run_command(*command))
    task = asyncio.create_task(operation)
    try:
        await asyncio.wait_for(entered.wait(), 5)
        monkeypatch.chdir(changed)
        monkeypatch.setenv("ORKET_COMMAND_INPUT_FIXTURE", "rotated")
        command[-1] = "raise SystemExit(9)"
        release.set()
        observed = await asyncio.wait_for(task, 5)
        stdout = observed if route == "inventory" else observed[1]
        assert json.loads(stdout) == [str(tmp_path), "captured"]
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("route", ["inventory", "packet1"])
async def test_output_limit_refuses_partial_output_after_cleanup(tmp_path, monkeypatch, route):
    monkeypatch.chdir(tmp_path)
    script = "import os,time; os.write(1,b'x'*(5*1024*1024)); time.sleep(20)"
    command = [sys.executable, "-c", script]
    operation = (_owned_inventory(inventory._run_command_sync, cmd=command, timeout_s=5)
                 if route == "inventory" else packet1._run_command(*command, timeout_seconds=5))
    with pytest.raises(CommandExecutionUncertain) as observed:
        await asyncio.wait_for(operation, 10)
    lifetime = observed.value.lifetime
    assert lifetime.reason == "output_limit" and lifetime.cleanup_confirmed and not lifetime.capture_complete
    assert 0 < len(lifetime.stdout) <= 4 * 1024 * 1024
    for pid in (lifetime.command_pid, lifetime.supervisor_pid, lifetime.transport_pid):
        assert not await asyncio.to_thread(psutil.pid_exists, pid)
