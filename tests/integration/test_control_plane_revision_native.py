"""Independent process contention and host-process interruption of shared state."""
import asyncio
import json
import sys

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


async def reap(processes):
    for process in processes:
        if process.returncode is None:
            process.kill()
    for process in processes:
        await asyncio.wait_for(process.communicate(), timeout=30)
        assert process.returncode is not None


@pytest.mark.parametrize("kind", KINDS)
# Layer: integration
async def test_native_observers_cannot_both_advance_shared_revision(tmp_path, kind):
    path = tmp_path / "control.sqlite3"
    repository = AsyncControlPlaneExecutionRepository(path)
    original = await save(repository, kind, initial(kind))
    updates = changed(original, kind).model_dump(mode="json")
    processes = []
    try:
        for _ in range(2):
            processes.append(await start_worker(path, kind, "race"))
        observed = await asyncio.gather(*(receive(process) for process in processes))
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
        await reap(processes)


@pytest.mark.parametrize("kind", KINDS)
# Layer: integration
async def test_process_death_before_commit_preserves_revision_and_allows_next_writer(tmp_path, kind):
    path = tmp_path / "control.sqlite3"
    repository = AsyncControlPlaneExecutionRepository(path)
    original = await save(repository, kind, initial(kind))
    process = await start_worker(path, kind, "interrupt")
    try:
        assert (await receive(process))["record"] == original.model_dump(mode="json")
        process.stdin.write((changed(original, kind).model_dump_json() + "\n").encode())
        await process.stdin.drain()
        assert await receive(process) == {"event": "uncommitted", "revision": 1}
        process.kill()
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        assert process.returncode != 0, stderr
        assert await read(repository, kind) == original
        assert (await save(repository, kind, changed(original, kind))).state_revision == 1
    finally:
        await reap([process])
