"""Layer: integration. Real process input, deadline, refusal and responsiveness proof."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from functools import partial

import aiosqlite
import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.command_runner import SandboxCommandTimeout, SandboxCommandUncertain
from orket.application.services.sandbox_command_composition import create_sandbox_command_runner
from tests.integration.test_sandbox_command_lifetime import standard_runner
from tests.integration.test_verification_process_lifetime import (
    WORKER,
    assert_stopped,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("sync", [False, True])
@pytest.mark.parametrize("exit_code", [0, 7])
async def test_sandbox_command_preserves_completed_status_and_text(tmp_path, sync, exit_code):
    runner = await standard_runner(tmp_path)
    command = (sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'hello\\r\\n'); "
               f"sys.stderr.write('diagnostic'); sys.exit({exit_code})")
    result = (await run_owned_thread(partial(runner.run_sync, *command), label="sandbox-sync-test")
              if sync else await runner.run_async(*command))
    assert (result.returncode, result.stdout, result.stderr) == (exit_code, "hello\n" if sync else "hello\r\n", "diagnostic")
    assert result.lifetime.reason == "completed" and result.lifetime.cleanup_confirmed
    assert result.lifetime.capture_complete


async def test_standard_sandbox_runner_captures_environment_and_cwd(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.chdir(first)
    monkeypatch.setenv("ORKET_COMMAND_TEST_INPUT", "captured")
    runner = await standard_runner(tmp_path)
    monkeypatch.chdir(second)
    monkeypatch.setenv("ORKET_COMMAND_TEST_INPUT", "rotated")
    result = await runner.run_async(sys.executable, "-c", "import os,json; "
        "print(json.dumps([os.getcwd(), os.environ['ORKET_COMMAND_TEST_INPUT']]))")
    assert json.loads(result.stdout) == [str(first), "captured"]


async def test_supplied_process_environment_is_complete_and_copied(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_COMMAND_AMBIENT_ONLY", "must-not-inherit")
    environment = {key: value for key, value in os.environ.items() if key != "ORKET_COMMAND_AMBIENT_ONLY"}
    environment["ORKET_COMMAND_TEST_INPUT"] = "captured"
    runner = create_sandbox_command_runner(tmp_path, environment=environment, cwd=tmp_path)
    environment["ORKET_COMMAND_TEST_INPUT"] = "rotated"
    result = await runner.run_async(sys.executable, "-c", "import os,json; "
        "print(json.dumps([os.environ['ORKET_COMMAND_TEST_INPUT'], os.getenv('ORKET_COMMAND_AMBIENT_ONLY')]))")
    assert json.loads(result.stdout) == ["captured", None]


@pytest.mark.parametrize("sync", [False, True])
async def test_native_deadline_owns_tree_and_allows_independent_sqlite(tmp_path, sync, record_property):
    runner = create_sandbox_command_runner(tmp_path, timeout_seconds=30 if sync else 5)
    command = (sys.executable, str(WORKER), str(tmp_path), "2", "detached", "ignore-term")
    operation = (run_owned_thread(partial(runner.run_sync, *command, timeout=5), label="sandbox-sync-deadline")
                 if sync else runner.run_async(*command))
    task, processes = asyncio.create_task(operation), []
    try:
        processes = await await_tree(tmp_path)
        started = asyncio.get_running_loop().time()
        async with aiosqlite.connect(tmp_path / "independent.db") as database:
            await database.execute("CREATE TABLE observed(value INTEGER)")
            await database.execute("INSERT INTO observed VALUES(17)")
            await database.commit()
            async with database.execute("SELECT value FROM observed") as cursor:
                assert await cursor.fetchone() == (17,)
        elapsed = asyncio.get_running_loop().time() - started
        record_property("competing_sqlite_seconds", elapsed)
        assert elapsed < 0.5
        with pytest.raises(SandboxCommandTimeout) as caught:
            await asyncio.wait_for(asyncio.shield(task), 10)
        assert caught.value.timeout == 5
        assert caught.value.lifetime.reason == "timeout" and caught.value.lifetime.cleanup_confirmed
        await assert_stopped(processes, tmp_path)
    finally:
        if not processes:
            processes = await asyncio.to_thread(observe_processes, tmp_path)
        await asyncio.to_thread(stop_observed, processes)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await assert_stopped(processes, tmp_path)


@pytest.mark.parametrize("case", ["launch", "output-limit"])
async def test_native_refusal_never_becomes_command_success(tmp_path, case):
    runner = await standard_runner(tmp_path)
    command = ((str(tmp_path / "nonexistent-executable"), "sensitive-argument") if case == "launch" else
               (sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x' * (5 * 1024 * 1024))"))
    with pytest.raises(SandboxCommandUncertain) as caught:
        await runner.run_async(*command)
    result = caught.value.lifetime
    assert result.cleanup_confirmed and not result.capture_complete
    assert result.reason == ("launch_failed" if case == "launch" else "output_limit")
    assert str(caught.value) == "E_SANDBOX_COMMAND_EXECUTION_UNCERTAIN"


@pytest.mark.parametrize("budget", [0, -1, float("inf"), float("nan")])
async def test_invalid_native_deadline_refuses_execution(tmp_path, budget):
    runner = create_sandbox_command_runner(tmp_path, cwd=tmp_path, timeout_seconds=budget)
    with pytest.raises(ValueError, match="E_VERIFICATION_COMMAND_TIMEOUT_INVALID"):
        await runner.run_async(sys.executable, "-c", "from pathlib import Path; Path('unexpected').touch()")
    assert not (tmp_path / "unexpected").exists()


async def test_sync_command_refuses_event_loop_before_launch(tmp_path):
    runner = create_sandbox_command_runner(tmp_path, cwd=tmp_path)
    with pytest.raises(RuntimeError, match="E_SANDBOX_COMMAND_REQUIRES_WORKER"):
        runner.run_sync(sys.executable, "-c", "from pathlib import Path; Path('unexpected').touch()")
    assert not (tmp_path / "unexpected").exists()
