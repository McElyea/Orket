"""Layer: integration. Actual child effects observe inputs frozen before transport scheduling."""
import asyncio
import json
import os
import sys
from pathlib import Path

import psutil
import pytest

from orket.application.services import command_process_supervisor as supervisor

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).with_name("provider_input_capture_worker.py")


def _roots(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    for root in (first, second):
        (root / "work").mkdir(parents=True)
    return first, second


@pytest.mark.parametrize("protocol", ["batch", "jsonl"])
async def test_owned_command_captures_borrowed_inputs_before_transport_task(tmp_path, monkeypatch, protocol):
    first, second = await asyncio.to_thread(_roots, tmp_path)
    monkeypatch.chdir(first)
    environment = dict(os.environ, ORKET_TEST_PROVIDER_INPUT="admitted")
    command = [sys.executable, str(WORKER), "exchange", protocol, "admitted"]
    requests = [b'{"value":"admitted"}\n']
    data = bytearray(requests[0])
    arrived, release = asyncio.Event(), asyncio.Event()
    original = supervisor.execute_owned_command

    async def held(**options):
        arrived.set()
        await asyncio.wait_for(release.wait(), 5)
        return await original(**options)

    monkeypatch.setattr(supervisor, "execute_owned_command", held)
    owner = supervisor.CommandProcessSupervisor(tmp_path, cancellation_event="input_capture_interrupted")
    options = dict(cwd=Path("work"), environment=environment)
    call = (owner.run(command, input_data=data, timeout_seconds=5, **options) if protocol == "batch"
            else owner.run_jsonl(command, requests=requests, io_timeout_seconds=5, **options))
    operation = asyncio.create_task(call)
    try:
        await asyncio.wait_for(arrived.wait(), 5)
        command[-1] = "changed"
        environment["ORKET_TEST_PROVIDER_INPUT"] = "changed"
        data[:] = b'{"value":"changed"}\n'
        requests[0] = bytes(data)
        monkeypatch.chdir(second)
        release.set()
        result = await asyncio.wait_for(asyncio.shield(operation), 10)
        assert result.cleanup_confirmed and result.capture_complete
        assert result.reason == "completed" and result.returncode == 0
        assert json.loads(result.stdout) == dict(marker="admitted", directory=str(first / "work"),
                                                 environment="admitted", request='{"value":"admitted"}\n')
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(operation, return_exceptions=True), 10)


def _private_owner(pid):
    owners = [parent for parent in psutil.Process(pid).parents()
              if any(Path(argument).name == "owned_command_worker.py" for argument in parent.cmdline())]
    assert owners
    return {owner.pid: dict(directory=owner.cwd(), environment=owner.environ().get("ORKET_TEST_PROVIDER_INPUT"))
            for owner in owners}


async def _await_pid(path):
    async with asyncio.timeout(5):
        for _ in range(500):
            if await asyncio.to_thread(path.exists):
                return int(await asyncio.to_thread(path.read_text))
            await asyncio.sleep(.01)
    raise AssertionError("Actual fixture process did not publish its identity")


@pytest.mark.parametrize("mode", ["ambient", "explicit", "empty"])
async def test_private_supervisor_uses_admitted_directory_and_environment(tmp_path, monkeypatch, mode):
    first, second = await asyncio.to_thread(_roots, tmp_path)
    monkeypatch.chdir(first)
    monkeypatch.setenv("ORKET_TEST_PROVIDER_INPUT", "admitted")
    environment = None if mode == "ambient" else (dict(os.environ) if mode == "explicit" else {})
    arrived, dispatch = asyncio.Event(), asyncio.Event()
    original = supervisor.execute_owned_command

    async def held(**options):
        arrived.set()
        await asyncio.wait_for(dispatch.wait(), 5)
        return await original(**options)

    monkeypatch.setattr(supervisor, "execute_owned_command", held)
    observed, release = tmp_path / "fixture.pid", tmp_path / "release"
    owner = supervisor.CommandProcessSupervisor(tmp_path, cancellation_event="context_capture_interrupted")
    operation = asyncio.create_task(owner.run(
        [sys.executable, str(WORKER), "owner", str(observed), str(release)], cwd=first / "work",
        timeout_seconds=10, environment=environment))
    try:
        await asyncio.wait_for(arrived.wait(), 5)
        monkeypatch.chdir(second)
        monkeypatch.setenv("ORKET_TEST_PROVIDER_INPUT", "changed")
        dispatch.set()
        observation = await asyncio.to_thread(_private_owner, await _await_pid(observed))
        expected = dict(directory=str(first / "work"), environment=None if mode == "empty" else "admitted")
        assert all(value == expected for value in observation.values())
        await asyncio.to_thread(release.touch)
        result = await asyncio.wait_for(asyncio.shield(operation), 5)
        assert result.cleanup_confirmed and result.capture_complete
        assert result.returncode == 0 and result.stdout.strip() == b"released"
        assert set(observation) == {result.supervisor_pid, result.transport_pid}
    finally:
        dispatch.set()
        await asyncio.to_thread(release.touch)
        await asyncio.wait_for(asyncio.gather(operation, return_exceptions=True), 10)
