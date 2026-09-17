"""Real command admission, retained byte bounds and cancellation observations."""
from __future__ import annotations

import asyncio
import sys

import pytest

from orket.adapters.execution.owned_command_process import execute_owned_command
from orket.application.services.command_process_supervisor import CommandProcessCancelled
from orket.application.services.runtime_verifier import RuntimeVerifier
from tests.integration.test_verification_process_lifetime import WORKER, assert_stopped, await_tree, stop_observed

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
async def test_already_stopped_admission_does_not_execute_a_command(tmp_path):
    stop = asyncio.Event()
    stop.set()
    result = await execute_owned_command(
        argv=[sys.executable, "-c", "from pathlib import Path; Path('unexpected').touch()"],
        cwd=tmp_path, environment=None, timeout_seconds=3, input_data=None, stop=stop)
    assert result.reason == "cancelled" and result.cleanup_confirmed is True
    assert result.command_pid is None
    assert not await asyncio.to_thread((tmp_path / "unexpected").exists)


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
# Layer: integration
async def test_excessive_raw_output_cannot_pass_or_admit_the_next_command(tmp_path, stream):
    result = await RuntimeVerifier(tmp_path, issue_params={"runtime_verifier": {
        "commands": [
            [sys.executable, "-c", f"import sys; sys.{stream}.buffer.write(b'x' * (5 * 1024 * 1024))"],
            [sys.executable, "-c", "from pathlib import Path; Path('unexpected').touch()"],
        ],
    }}).verify()
    assert not result.ok and result.failure_breakdown == {"output_limit": 1}
    assert len(result.command_results) == 1
    receipt = result.command_results[0]
    assert receipt["returncode"] == 125
    assert receipt[f"{stream}_bytes"] == 4 * 1024 * 1024
    assert receipt["process_lifetime"]["capture_complete"] is False
    assert receipt["process_lifetime"]["cleanup_confirmed"] is True
    assert not await asyncio.to_thread((tmp_path / "unexpected").exists)


# Layer: integration
async def test_missing_executable_retains_launch_and_cleanup_observation(tmp_path):
    result = await RuntimeVerifier(tmp_path, issue_params={"runtime_verifier": {
        "commands": [[str(tmp_path / "absent-executable")]],
    }}).verify()
    receipt = result.command_results[0]
    assert not result.ok and receipt["failure_class"] == "missing_runtime"
    assert receipt["returncode"] == 127
    assert receipt["process_lifetime"]["reason"] == "launch_failed"
    assert receipt["process_lifetime"]["cleanup_confirmed"] is True
    assert receipt["process_lifetime"]["command_pid"] is None
    assert receipt["process_lifetime"]["diagnostics"]


# Layer: integration
async def test_cancellation_exception_retains_observed_cleanup_for_its_caller(tmp_path):
    verifier = RuntimeVerifier(tmp_path, issue_params={"runtime_verifier": {
        "commands": [[sys.executable, str(WORKER), str(tmp_path), "2"]],
    }})
    task = asyncio.create_task(verifier.verify())
    processes = await await_tree(tmp_path)
    try:
        task.cancel()
        with pytest.raises(CommandProcessCancelled) as cancelled:
            await task
        assert cancelled.value.lifetime.cleanup_confirmed is True
        await assert_stopped(processes, tmp_path)
    finally:
        await asyncio.to_thread(stop_observed, processes)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
