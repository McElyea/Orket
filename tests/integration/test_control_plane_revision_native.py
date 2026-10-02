"""Independent process contention and host-process interruption of shared state."""
import asyncio
import json
import sys

import psutil
import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from tests.integration.test_control_plane_state_revision import KINDS, changed, initial, read, save

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def start_worker(path, kind, mode):
    return await asyncio.create_subprocess_exec(
        sys.executable, "-m", "tests.helpers.control_plane_revision_worker", str(path), kind, mode,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )


async def receive(process):
    line = await asyncio.wait_for(process.stdout.readline(), timeout=30)
    assert line, (process.returncode, await process.stderr.read())
    return json.loads(line)


def capture_worker(launcher_pid, worker_pid):
    worker = psutil.Process(worker_pid)
    assert worker.is_running()
    assert worker.pid == launcher_pid or launcher_pid in {parent.pid for parent in worker.parents()}
    return worker


async def reap(processes, workers):
    for worker in workers:
        if await asyncio.to_thread(worker.is_running):
            try:
                await asyncio.to_thread(worker.kill)
            except psutil.NoSuchProcess:
                assert not await asyncio.to_thread(worker.is_running)
    for process in processes:
        if process.returncode is None:
            process.kill()
    for process in processes:
        await asyncio.wait_for(process.communicate(), timeout=30)
        assert process.returncode is not None
    for worker in workers:
        await asyncio.to_thread(worker.wait, 30)
        assert not await asyncio.to_thread(worker.is_running)


@pytest.mark.parametrize("kind", KINDS)
# Layer: integration
async def test_native_observers_cannot_both_advance_shared_revision(tmp_path, kind):
    path = tmp_path / "control.sqlite3"
    repository = AsyncControlPlaneExecutionRepository(path)
    original = await save(repository, kind, initial(kind))
    updates = changed(original, kind).model_dump(mode="json")
    processes = []
    workers = []
    try:
        for _ in range(2):
            processes.append(await start_worker(path, kind, "race"))
        observed = await asyncio.gather(*(receive(process) for process in processes))
        for process, item in zip(processes, observed, strict=True):
            workers.append(await asyncio.to_thread(capture_worker, process.pid, item["pid"]))
        assert len({item["pid"] for item in observed}) == 2
        assert all(item["record"] == original.model_dump(mode="json") for item in observed)
        # Both children have retained revision zero before either can write.
        for process in processes:
            process.stdin.write((json.dumps(updates) + "\n").encode())
            await process.stdin.drain()
        results = await asyncio.gather(*(receive(process) for process in processes))
        outputs = await asyncio.gather(*(asyncio.wait_for(p.communicate(), 30) for p in processes))
        assert all(p.returncode == 0 for p in processes), outputs
        assert sorted(item["event"] for item in results) == ["refused", "saved"]
        refused = next(item for item in results if item["event"] == "refused")
        assert "E_CONTROL_PLANE_STATE_CONFLICT" in refused["error"]
        saved = next(item["record"] for item in results if item["event"] == "saved")
        assert saved["state_revision"] == 1
        assert (await read(repository, kind)).model_dump(mode="json") == saved
    finally:
        await reap(processes, workers)


@pytest.mark.parametrize("kind", KINDS)
# Layer: integration
async def test_process_death_before_commit_preserves_revision_and_allows_next_writer(tmp_path, kind, record_property):
    path = tmp_path / "control.sqlite3"
    repository = AsyncControlPlaneExecutionRepository(path)
    original = await save(repository, kind, initial(kind))
    process = await start_worker(path, kind, "interrupt")
    workers = []
    try:
        observed = await receive(process)
        worker = await asyncio.to_thread(capture_worker, process.pid, observed["pid"])
        workers.append(worker)
        record_property("launcher_pid", process.pid)
        record_property("worker_pid", worker.pid)
        record_property("worker_created", await asyncio.to_thread(worker.create_time))
        assert observed["record"] == original.model_dump(mode="json")
        process.stdin.write((changed(original, kind).model_dump_json() + "\n").encode())
        await process.stdin.drain()
        assert await receive(process) == {"event": "uncommitted", "revision": 1}
        # Windows venv launchers can have a different PID from the SQLite owner.
        await asyncio.to_thread(worker.kill)
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        assert process.returncode != 0, stderr
        await asyncio.to_thread(worker.wait, 30)
        assert not await asyncio.to_thread(worker.is_running)
        record_property("worker_terminated_before_recovery", True)
        assert await read(repository, kind) == original
        assert (await save(repository, kind, changed(original, kind))).state_revision == 1
    finally:
        await reap([process], workers)
