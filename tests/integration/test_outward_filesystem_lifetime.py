"""Layer: integration. Direct connector cancellation must retain filesystem workers."""
from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY, BuiltInConnectorRegistry
from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.runtime import CompositionConfig, create_api_app

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def held_filesystem_operation(tmp_path, monkeypatch, connector):
    target = tmp_path / "target"
    if connector == "delete_file":
        await asyncio.to_thread(target.write_text, "owned effect", encoding="utf-8")
    entered, release, finished = Event(), Event(), Event()
    method = "unlink" if connector == "delete_file" else "mkdir"
    original = getattr(Path, method)
    held_path = tmp_path if connector == "write_file" else target

    def held_operation(path, *args, **kwargs):
        if path != held_path:
            return original(path, *args, **kwargs)
        entered.set()
        try:
            assert release.wait(10), "Filesystem fixture was not released"
            return original(path, *args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(Path, method, held_operation)
    args = {"path": target.name}
    if connector == "write_file":
        args["content"] = "owned effect"
    return target, entered, release, finished, args


@pytest.mark.parametrize("connector", ["delete_file", "create_directory", "write_file"])
@pytest.mark.parametrize("stop", ["cancel", "repeated-cancel", "timeout"])
# Layer: integration
async def test_direct_filesystem_waits_for_actual_worker(tmp_path, monkeypatch, stop, connector):
    target, entered, release, finished, args = await held_filesystem_operation(tmp_path, monkeypatch, connector)
    metadata = replace(DEFAULT_BUILTIN_CONNECTOR_REGISTRY.get(connector),
                       timeout_seconds=0.1 if stop == "timeout" else 10)
    service = OutwardConnectorService(connector_registry=BuiltInConnectorRegistry([metadata]), workspace_root=tmp_path)
    invocation = asyncio.create_task(service.invoke(connector, args))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if stop != "timeout":
            invocation.cancel()
        if stop == "repeated-cancel":
            for _ in range(3):
                await asyncio.sleep(0)
                invocation.cancel()
        completed, _ = await asyncio.wait({invocation}, timeout=0.2)
        assert not completed, "Connector settled while its filesystem thread could still mutate the target"
        assert not finished.is_set()
        assert await asyncio.to_thread(target.exists) is (connector == "delete_file")
    finally:
        release.set()
        outcome, = await asyncio.gather(invocation, return_exceptions=True)
        assert await asyncio.to_thread(finished.wait, 5)
        assert await asyncio.to_thread(target.exists) is (connector != "delete_file")
    if stop == "timeout":
        assert outcome["outcome"] == "timeout"
    else:
        assert isinstance(outcome, asyncio.CancelledError)


# Layer: integration
async def test_api_request_close_waits_for_direct_filesystem_worker(tmp_path, monkeypatch):
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    owner = app.state.api_runtime_context
    target, entered, release, finished, args = await held_filesystem_operation(tmp_path, monkeypatch, "delete_file")
    service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY, workspace_root=tmp_path)
    caller = asyncio.create_task(owner.run_request(lambda: service.invoke("delete_file", args)))
    closing = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        closing = asyncio.create_task(owner.close())
        completed, _ = await asyncio.wait({closing}, timeout=0.2)
        assert not completed and not owner.closed and not finished.is_set()
        caller.cancel()
        await asyncio.sleep(0)
        caller.cancel()
        assert not caller.done() and owner.active_request_count == 1
    finally:
        release.set()
        await asyncio.gather(caller, return_exceptions=True)
        await (closing if closing is not None else owner.close())
    assert owner.closed and finished.is_set() and not await asyncio.to_thread(target.exists)
