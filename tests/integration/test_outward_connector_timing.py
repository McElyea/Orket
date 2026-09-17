"""Compare native connector observations with independent elapsed/process evidence."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import replace

import psutil
import pytest

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY, BuiltInConnectorRegistry
from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.core.contracts.invocation_timing import read_invocation_timing

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("fails_on", [1, 2])
# Layer: integration
async def test_clock_failure_preserves_real_file_effect_and_unavailable_observation(tmp_path, fails_on):
    calls = []

    def clock():
        calls.append(1)
        if len(calls) == fails_on:
            raise OSError("clock unavailable")
        return 10

    service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path, monotonic_ns=clock)
    event = await service.invoke("write_file", {"path": "observed.txt", "content": "retained effect"})
    assert event["outcome"] == "success"
    assert await asyncio.to_thread((tmp_path / "observed.txt").read_text, encoding="utf-8") == "retained effect"
    observed = read_invocation_timing(event)
    assert observed.duration_ms is None and observed.timing.reason == "clock_unavailable"


def service_for(root, timeout=5):
    command = replace(DEFAULT_BUILTIN_CONNECTOR_REGISTRY.get("run_command"), timeout_seconds=timeout)
    return OutwardConnectorService(connector_registry=BuiltInConnectorRegistry([command]), workspace_root=root)


def assert_measured(event, elapsed_ms, minimum):
    observation = read_invocation_timing(event)
    assert observation.timing.status == "measured"
    assert observation.timing.clock == "python.time.perf_counter_ns"
    assert observation.timing.scope == "awaited_connector_invocation"
    # Outer observation includes schema validation/projection; permit 50 ms of
    # that work plus scheduling, but never a zero for the deliberate slow call.
    assert minimum <= observation.duration_ms <= elapsed_ms + 1
    assert elapsed_ms - observation.duration_ms <= 50


@pytest.mark.parametrize("returncode", [0, 7])
# Layer: integration
async def test_native_command_success_and_failure_have_measured_duration(tmp_path, returncode):
    service = service_for(tmp_path)
    start = time.perf_counter_ns()
    event = await service.invoke("run_command", {"command": [sys.executable, "-c",
        f"import time,sys; time.sleep(0.3); print('observed'); sys.exit({returncode})"]})
    elapsed = (time.perf_counter_ns() - start) / 1_000_000
    assert event["outcome"] == ("success" if returncode == 0 else "failed")
    assert event["result_summary"]["returncode"] == returncode
    assert_measured(event, elapsed, 300)


# Layer: integration
async def test_native_command_timeout_includes_awaited_cleanup_time(tmp_path):
    service = service_for(tmp_path, timeout=0.2)
    start = time.perf_counter_ns()
    event = await service.invoke("run_command", {"command": [sys.executable, "-c", "import time; time.sleep(5)"]})
    elapsed = (time.perf_counter_ns() - start) / 1_000_000
    assert event["outcome"] == "timeout"
    assert_measured(event, elapsed, 199)


# Layer: integration
async def test_native_command_cancellation_logs_measurement_without_returned_effect(tmp_path, caplog):
    service = service_for(tmp_path)
    marker = tmp_path / "started.json"
    command = [sys.executable, "-c", "import os,pathlib,json,time; "
        "pathlib.Path('started.json').write_text(json.dumps({'pid':os.getpid()})); time.sleep(5)"]
    start = time.perf_counter_ns()
    task = asyncio.create_task(service.invoke("run_command", {"command": command}))
    child = None
    try:
        async with asyncio.timeout(3):
            while not await asyncio.to_thread(marker.exists):
                if task.done():
                    pytest.fail(f"Connector stopped before native marker: {task.result()}")
                await asyncio.sleep(0.01)
        child = psutil.Process(json.loads(await asyncio.to_thread(marker.read_text, encoding="utf-8"))["pid"])
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        elapsed = (time.perf_counter_ns() - start) / 1_000_000
        events = [row.orket_record["data"] for row in caplog.records if row.message == "outward_connector_interrupted"]
        event, = events
        assert event["observation"] == "cancelled" and "outcome" not in event
        assert_measured(event, elapsed, 100)
        assert event["runtime_event"]["timing"] == event["timing"]
        assert event["runtime_event"]["duration_ms"] == event["duration_ms"]
        assert not await asyncio.to_thread(child.is_running)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        if child is not None and await asyncio.to_thread(child.is_running):
            await asyncio.to_thread(child.kill)
            await asyncio.to_thread(child.wait, timeout=3)
