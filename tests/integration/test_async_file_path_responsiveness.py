"""Integration: native file-tool path observation must leave the loop responsive."""
import asyncio
import threading
import time
from functools import partial
from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.tools.families.filesystem import FileSystemTools
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_connector_service import OutwardConnectorService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def prepare_file_operation(root, operation, layer):
    target = root / ("directory" if operation in {"create_directory", "list_directory"} else "target.txt")
    if operation in {"read_file", "delete_file"}:
        await asyncio.to_thread(target.write_text, "native payload", encoding="utf-8")
    elif operation == "list_directory":
        await asyncio.to_thread(target.mkdir)
    if layer == "connector":
        service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY, workspace_root=root)
        return target, partial(service.invoke, operation, {"path": target.name})
    adapter = AsyncFileTools(root) if layer == "adapter" else FileSystemTools(root, [])
    args = [target.name] if layer == "adapter" else [{"path": target.name}]
    if operation == "write_file":
        if layer == "adapter":
            args.append("native payload")
        else:
            args[0]["content"] = "native payload"
    return target, partial(getattr(adapter, operation), *args)


@pytest.mark.parametrize("operation,layer", [
    (operation, layer) for operation in ("read_file", "write_file", "create_directory", "list_directory")
    for layer in ("adapter", "family")
] + [("delete_file", "connector")])
async def test_file_path_observation_is_owned_worker_work(tmp_path, monkeypatch, record_property, layer, operation):
    target, invoke = await prepare_file_operation(tmp_path, operation, layer)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = Path.resolve

    def held_resolve(path, *args, **kwargs):
        if path != target or entered.is_set():
            return original(path, *args, **kwargs)
        entered.set()
        try:
            assert release.wait(5), "Native path observation was not released"
            return original(path, *args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(Path, "resolve", held_resolve)
    timer = threading.Timer(.8, release.set)
    timer.start()
    started = time.perf_counter()
    task = asyncio.create_task(invoke())
    try:
        async with asyncio.timeout(5):
            while not entered.is_set():
                if task.done():
                    pytest.fail(f"File operation returned before native observation: {await task}")
                await asyncio.sleep(.001)
        async with aiosqlite.connect(tmp_path / "responsive.sqlite3") as connection:
            assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
        elapsed = time.perf_counter() - started
        record_property("responsive_sqlite_seconds", elapsed)
        assert elapsed < .5
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(.05)
        assert not task.done() and not finished.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
    finally:
        release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(finished.wait, 5)
    assert not timer.is_alive()
