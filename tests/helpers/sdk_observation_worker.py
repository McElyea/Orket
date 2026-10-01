"""Isolated real SDK result and required native lifetime publication controls."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import threading
from pathlib import Path

import psutil
import pytest

import orket
from orket.adapters.execution import owned_io
from orket.adapters.observability import log_publication, logging_context
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.extensions import sdk_workload_runner
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.lifetime_finalizer_native import (
    AppendHold,
    arrange_finalizer_interruption,
    await_ready,
    healthy_next_command,
)
from tests.helpers.log_process_receipts import process_readback
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.helpers.sdk_diagnostic_controls import failure_for
from tests.helpers.sdk_observation_controls import (
    EVENT,
    UNCERTAIN,
    assert_public_outcome,
    observe_actual_owners,
    prepare_request,
    public_caller,
    read_records,
)


async def before_release(root, state, hold, identity, mode):
    lifetime = state.lifetime
    assert lifetime.reason == "completed" and lifetime.returncode == {"success": 0, "error": 1, "missing": 23}[mode]
    assert lifetime.cleanup_confirmed and lifetime.capture_complete and hold.record["data"]["command_pid"] == lifetime.command_pid
    pids = [row["pid"] for row in identity["processes"]]
    assert pids.index(lifetime.command_pid) < pids.index(lifetime.supervisor_pid) <= pids.index(lifetime.transport_pid)
    processes = await asyncio.to_thread(process_readback,
        {row["pid"]: row["create_time"] for row in identity["processes"]})
    assert processes and all(row["status"] in {"absent", "reused"} for row in processes.values())
    exchange = state.exchange.root
    request = await asyncio.to_thread((exchange / "request.json").read_bytes)
    raw = None if mode == "missing" else await asyncio.to_thread((exchange / "result.json").read_bytes)
    child = json.loads(raw) if raw is not None else None
    assert state.reads == state.removes == 0 and not state.selected
    assert await asyncio.to_thread((root / "sdk-effect").read_text, encoding="utf-8") == "executed"
    assert json.loads(request)["context"]["workspace_root"] == str(root)
    if child is not None:
        assert child["ok"] is (mode == "success") and isinstance(child["capability_report"], dict)
    else:
        assert not await asyncio.to_thread((exchange / "result.json").exists)
    await asyncio.to_thread(write_payload_with_diff_ledger, root / "process-before-release.json", {
        "live_lineage": identity, "lifetime": lifetime.lifetime(), "returncode": lifetime.returncode,
        "processes": processes, "exchange": str(exchange), "request_sha256": hashlib.sha256(request).hexdigest(),
        "result_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
        "product_result_reads": state.reads, "product_exchange_removes": state.removes})
    return processes, request, raw, child


async def assert_physical_outcome(root, state, hold, graph, request, raw):
    records = await read_records(root / "orket.log")
    observed, = [row for row in records if row["event"] == EVENT]
    projected = {key: value for key, value in observed["data"].items() if key != "runtime_event"}
    assert projected == state.lifetime.lifetime() and observed["timestamp"].endswith("-07:00")
    uncertain = [row for row in records if row["event"] == UNCERTAIN]
    assert len(uncertain) == int(graph["uncertainty"])
    if uncertain:
        assert uncertain[0]["data"]["process_lifetime"] == state.lifetime.lifetime()
        assert uncertain[0]["data"]["phase"] == graph["phase"]
        assert uncertain[0]["data"]["exchange_path"] == str(state.exchange.root)
        assert uncertain[0]["timestamp"].endswith("-07:00")
        assert await asyncio.to_thread((state.exchange.root / "request.json").read_bytes) == request
        if raw is not None:
            assert await asyncio.to_thread((state.exchange.root / "result.json").read_bytes) == raw
        else:
            assert not await asyncio.to_thread((state.exchange.root / "result.json").exists)
    else:
        assert not await asyncio.to_thread(state.exchange.root.exists)
    assert hold.calls == 1 and hold.finished.is_set() and not hold.expired
    assert not await asyncio.to_thread((root / "late/orket.log").exists)
    return {"physical_observed_record": True, "physical_uncertainty_records": len(uncertain),
            "exchange_retained": graph["uncertainty"], "public_workspace_capture_retained": True}


async def observe(root, kind, stop, mode, monkeypatch, observations):
    failure = failure_for(kind)
    cause = failure.__cause__ if failure is not None else None
    hold = AppendHold(EVENT, failure)
    hold.install(monkeypatch)
    state = observe_actual_owners(monkeypatch)
    options = await asyncio.to_thread(prepare_request, root, mode)
    active = asyncio.create_task(public_caller(sdk_workload_runner.run_sdk_workload_in_subprocess(**options)))
    waiter = active
    try:
        identity = await await_ready(root / "ready.json", active)
        options["sdk_ctx"].workspace_root = root / "late"
        options["input_payload"]["mode"] = "mutated after dispatch"
        await asyncio.to_thread((root / "release-sdk").touch)
        assert await asyncio.to_thread(hold.entered.wait, 10), "actual observed publication was not reached"
        processes, request, raw, child = await before_release(root, state, hold, identity, mode)
        waiter = await arrange_finalizer_interruption(active, stop)
        elapsed = await sqlite_response(root / "responsive.sqlite3",
            lambda name, value: observations.append({"name": name, "value": value}))
        assert elapsed < .5
        done, _ = await asyncio.wait({waiter}, timeout=.1)
        assert not done and not active.done() and not hold.finished.is_set()
        assert active.cancelling() == {"none": 0, "cancel": 2, "timeout": 1}[stop]
        assert hold.worker != threading.get_ident() and not hold.expired
        hold.release.set()
        outcome = await asyncio.wait_for(waiter, 10)
        graph = assert_public_outcome(outcome, state, failure, cause, stop, mode, child)
        physical = await assert_physical_outcome(root, state, hold, graph, request, raw)
        healthy = await healthy_next_command(root)
        return {"kind": kind, "stop": stop, "mode": mode, "caller_cancel_requests": active.cancelling(),
            "live_lineage": identity, "processes_before_release": processes, "lifetime": state.lifetime.lifetime(),
            "returncode": state.lifetime.returncode, "exchange_path": str(state.exchange.root),
            "request_sha256": hashlib.sha256(request).hexdigest(),
            "result_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
            "task_settled_before_emergency": active.done(), "healthy_next_lifetime": healthy, **graph, **physical}
    finally:
        hold.release.set()
        await asyncio.to_thread((root / "release-sdk").touch)
        if not active.done():
            active.cancel("fixture emergency cancellation")
        await asyncio.wait_for(asyncio.gather(active, waiter, return_exceptions=True), 10)


async def exercise(root, kind, stop, mode):
    prepared = await logging_context.prepare_logging(LoggingInputs(root, timezone_name="MST"))
    observations = []
    with pytest.MonkeyPatch.context() as monkeypatch, logging_context.bind_logging(prepared):
        result = await observe(root, kind, stop, mode, monkeypatch, observations)
    assert logging_context.selected_logging(required=False) is None
    assert log_publication._log_writer_thread.is_alive() and log_publication._log_write_queue.qsize() == 0
    return {**result, "observations": observations, "logging_binding_restored": True,
            "writer_shutdown": "process-exit; no in-process stop or join"}


def main():
    root, kind, stop, mode = Path(sys.argv[1]).resolve(), *sys.argv[2:]
    result = asyncio.run(exercise(root, kind, stop, mode))
    process = psutil.Process()
    modules = (owned_io, sdk_workload_runner, log_publication)
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
        owner_origin=str(Path(owned_io.__file__).resolve()),
        owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest(),
        process_identity={"pid": process.pid, "create_time": process.create_time()},
        source_origins={module.__name__: {"path": str(Path(module.__file__).resolve()),
            "sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()} for module in modules})
    child_source = Path(sdk_workload_runner.__file__).with_name("sdk_workload_subprocess.py").resolve()
    result["child_source"] = {"path": str(child_source), "sha256": hashlib.sha256(child_source.read_bytes()).hexdigest()}
    write_payload_with_diff_ledger(root / "result.json", result)


if __name__ == "__main__":
    main()
