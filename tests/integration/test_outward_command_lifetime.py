"""Layer: integration. Real outward commands must settle their entire owned tree."""
from __future__ import annotations

import asyncio
import sys
from dataclasses import replace

import psutil
import pytest

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY, BuiltInConnectorRegistry
from orket.application.services.outward_connector_service import OutwardConnectorService
from tests.integration.test_verification_process_lifetime import (
    WORKER,
    assert_stopped,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("stop", ["cancel", "repeated-cancel", "timeout", "leader-exit", "leader-failure"])
@pytest.mark.parametrize("flags", [[], ["detached", "ignore-term"]], ids=["ordinary", "detached-resistant"])
# Layer: integration
async def test_outward_command_stops_children_and_grandchildren(tmp_path, stop, flags, caplog):
    metadata = replace(DEFAULT_BUILTIN_CONNECTOR_REGISTRY.get("run_command"),
                       timeout_seconds=1 if stop == "timeout" else 10)
    service = OutwardConnectorService(connector_registry=BuiltInConnectorRegistry([metadata]), workspace_root=tmp_path)
    task = asyncio.create_task(service.invoke("run_command", {
        "command": [sys.executable, str(WORKER), str(tmp_path), "2", *flags, stop]}))
    processes = []
    try:
        processes = await await_tree(tmp_path)
        if stop in {"cancel", "repeated-cancel"}:
            task.cancel()
            if stop == "repeated-cancel":
                for _ in range(20):
                    if task.done():
                        break
                    await asyncio.sleep(0.01)
                    task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
            event, = [row.orket_record["data"] for row in caplog.records
                      if row.message == "outward_connector_interrupted"]
            assert event["observation"] == "cancelled" and "outcome" not in event
        else:
            if stop in {"leader-exit", "leader-failure"}:
                await asyncio.to_thread((tmp_path / "release-leader").touch)
            event = await asyncio.wait_for(asyncio.shield(task), 5)
            assert event["outcome"] == {"timeout": "timeout", "leader-exit": "success", "leader-failure": "failed"}[stop]
        # Observe actual process/effect lifetime before checking receipt shape.
        await assert_stopped(processes, tmp_path)
        lifetime = (event["process_lifetime"] if stop in {"cancel", "repeated-cancel"}
                    else event["result_summary"]["process_lifetime"])
        assert event["timing"]["status"] == "measured" and event["duration_ms"] > 0
        assert lifetime["cleanup_confirmed"] is True
        assert lifetime["backend"] == ("windows_job" if sys.platform == "win32" else "linux_subreaper")
        assert not await asyncio.to_thread(psutil.pid_exists, lifetime["supervisor_pid"])
        assert not await asyncio.to_thread(psutil.pid_exists, lifetime["transport_pid"])
    finally:
        if not processes:
            processes = await asyncio.to_thread(observe_processes, tmp_path)
        await asyncio.to_thread(stop_observed, processes)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
