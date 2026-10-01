"""Isolated SDK child removal failures, partial effects and exact public outcomes."""
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
from orket.settings import set_runtime_settings_context
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.lifetime_finalizer_native import arrange_finalizer_interruption, await_ready, healthy_next_command
from tests.helpers.log_process_receipts import process_readback
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.helpers.sdk_observation_controls import EVENT, UNCERTAIN, observe_actual_owners, public_caller, read_records
from tests.helpers.sdk_removal_controls import (
    RemovalHold,
    assert_removal_outcome,
    call_with_ambient_exception,
    observe_adoption,
    prepare_operation,
    remaining_bytes,
    removal_failure,
)
from tests.integration.test_sdk_process_control_plane import retained_records


async def before_release(root, state, hold, identity, mode):
    lifetime = state.lifetime
    assert lifetime.reason == "completed" and lifetime.returncode == (1 if mode == "error" else 0)
    assert lifetime.cleanup_confirmed and lifetime.capture_complete
    pids = [row["pid"] for row in identity["processes"]]
    assert pids.index(lifetime.command_pid) < pids.index(lifetime.supervisor_pid) <= pids.index(lifetime.transport_pid)
    processes = await asyncio.to_thread(process_readback,
        {row["pid"]: row["create_time"] for row in identity["processes"]})
    assert processes and all(row["status"] in {"absent", "reused"} for row in processes.values())
    exchange = state.exchange.root
    request = await asyncio.to_thread((exchange / "request.json").read_bytes)
    raw = await asyncio.to_thread((exchange / "result.json").read_bytes)
    child = json.loads(raw)
    assert child["ok"] is (mode != "error") and isinstance(child["capability_report"], dict)
    assert state.reads == state.removes == 1 and not state.selected
    assert (state.body_error is not None) is (mode == "error")
    assert (state.adopted is not None) is (mode != "error")
    assert await asyncio.to_thread((root / "sdk-effect").read_text) == "executed"
    assert json.loads(request)["context"]["workspace_root"] == str(root)
    assert hold.worker != threading.get_ident() and hold.calls == 1 and not hold.finished.is_set()
    await asyncio.to_thread(write_payload_with_diff_ledger, root / "process-before-release.json", {
        "live_lineage": identity, "lifetime": lifetime.lifetime(), "returncode": lifetime.returncode,
        "processes": processes, "exchange": str(exchange), "request_sha256": hashlib.sha256(request).hexdigest(),
        "result_sha256": hashlib.sha256(raw).hexdigest(), "product_result_reads": state.reads,
        "product_exchange_removes": state.removes, "selected_body_error": type(state.body_error).__name__})
    return processes, request, raw, child


async def physical_and_control_plane(root, state, request, raw, route):
    remaining = await asyncio.to_thread(remaining_bytes, state.exchange.root)
    records = await read_records(root / "orket.log")
    observed, = [row for row in records if row["event"] == EVENT]
    assert {key: value for key, value in observed["data"].items() if key != "runtime_event"} == state.lifetime.lifetime()
    uncertain = [row for row in records if row["event"] == UNCERTAIN]
    control = None
    if route == "manager":
        run, attempt, checkpoint, final, effects = await retained_records(root)
        control = {"run_state": run.lifecycle_state.value, "attempt_state": attempt.attempt_state.value,
            "resumability": checkpoint.resumability_class.value, "final_truth_present": final is not None,
            "effect_count": len(effects)}
    inventory = {"exchange_exists": remaining["exists"], "request_retained": remaining["request"] is not None,
        "result_retained": remaining["result"] is not None,
        "request_sha256": hashlib.sha256(remaining["request"]).hexdigest() if remaining["request"] is not None else None,
        "result_sha256": hashlib.sha256(remaining["result"]).hexdigest() if remaining["result"] is not None else None,
        "physical_uncertainty_count": len(uncertain), "control_plane": control}
    await asyncio.to_thread(write_payload_with_diff_ledger, root / "removal-after-settlement.json", inventory)
    if remaining["request"] is not None:
        assert remaining["request"] == request
    if remaining["result"] is not None:
        assert remaining["result"] == raw
    return inventory, uncertain


def assert_physical_result(inventory, uncertain, state, failure, stage):
    retained = failure is not None and stage != "after"
    assert inventory["exchange_exists"] is retained
    assert inventory["request_retained"] is (retained and stage != "partial")
    assert inventory["result_retained"] is retained
    assert len(uncertain) == int(failure is not None)
    if uncertain:
        event, = uncertain
        assert event["data"]["phase"] == "exchange-remove"
        assert event["data"]["exchange_path"] == str(state.exchange.root)
        assert event["data"]["process_lifetime"] == state.lifetime.lifetime()
    if inventory["control_plane"] is not None:
        assert inventory["control_plane"] == {"run_state": "executing", "attempt_state": "attempt_executing",
            "resumability": "resume_forbidden", "final_truth_present": False, "effect_count": 1}


async def observe(root, route, kind, stop, mode, stage, monkeypatch, observations):
    operation = await prepare_operation(root, route, mode)
    state = observe_actual_owners(monkeypatch)
    observe_adoption(monkeypatch, state)
    failure = removal_failure(kind)
    cause = failure.__cause__ if failure is not None else None
    hold = RemovalHold(state, stage, failure)
    hold.install(monkeypatch)
    caller = call_with_ambient_exception if mode == "ambient" else public_caller
    active = asyncio.create_task(caller(operation))
    waiter = active
    try:
        identity = await await_ready(root / "ready.json", active)
        await asyncio.to_thread((root / "release-sdk").touch)
        assert await asyncio.to_thread(hold.entered.wait, 10), "actual native rmtree was not reached"
        processes, request, raw, child = await before_release(root, state, hold, identity, mode)
        waiter = await arrange_finalizer_interruption(active, stop)
        assert await sqlite_response(root / "responsive.sqlite3",
            lambda name, value: observations.append({"name": name, "value": value})) < .5
        done, _ = await asyncio.wait({waiter}, timeout=.1)
        assert not done and not active.done() and not hold.finished.is_set()
        assert active.cancelling() == {"none": 0, "cancel": 2, "timeout": 1}[stop]
        hold.release.set()
        outcome = await asyncio.wait_for(waiter, 10)
        inventory, uncertain = await physical_and_control_plane(root, state, request, raw, route)
        graph = assert_removal_outcome(outcome, state, failure, cause, stop, mode, child)
        assert_physical_result(inventory, uncertain, state, failure, stage)
        assert hold.finished.is_set() and hold.calls == 1 and not hold.expired
        healthy = await healthy_next_command(root)
        return {"route": route, "kind": kind, "stop": stop, "mode": mode, "stage": stage,
            "caller_cancel_requests": active.cancelling(), "live_lineage": identity,
            "processes_before_release": processes, "lifetime": state.lifetime.lifetime(),
            "returncode": state.lifetime.returncode, "exchange_path": str(state.exchange.root),
            "task_settled_before_emergency": active.done(), "healthy_next_lifetime": healthy,
            "ambient_caller_exception_guard": mode == "ambient", **graph, **inventory}
    finally:
        hold.release.set()
        await asyncio.to_thread((root / "release-sdk").touch)
        if not active.done():
            active.cancel("fixture emergency cancellation")
        await asyncio.wait_for(asyncio.gather(active, waiter, return_exceptions=True), 10)


async def exercise(root, route, kind, stop, mode, stage):
    prepared = await logging_context.prepare_logging(LoggingInputs(root, timezone_name="MST"))
    observations = []
    with pytest.MonkeyPatch.context() as monkeypatch, logging_context.bind_logging(prepared):
        monkeypatch.setenv("ORKET_DURABLE_ROOT", str(root / ".orket/durable"))
        set_runtime_settings_context(user_settings={}, user_preferences={})
        result = await observe(root, route, kind, stop, mode, stage, monkeypatch, observations)
    assert logging_context.selected_logging(required=False) is None
    assert log_publication._log_writer_thread.is_alive() and log_publication._log_write_queue.qsize() == 0
    return {**result, "observations": observations, "logging_binding_restored": True,
            "writer_shutdown": "process-exit; no in-process stop or join"}


def main():
    root = Path(sys.argv[1]).resolve()
    result = asyncio.run(exercise(root, *sys.argv[2:]))
    process = psutil.Process()
    modules = (owned_io, sdk_workload_runner, log_publication)
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
        owner_origin=str(Path(owned_io.__file__).resolve()),
        owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest(),
        process_identity={"pid": process.pid, "create_time": process.create_time()},
        source_origins={module.__name__: {"path": str(Path(module.__file__).resolve()),
            "sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()} for module in modules})
    child = Path(sdk_workload_runner.__file__).with_name("sdk_workload_subprocess.py").resolve()
    result["child_source"] = {"path": str(child), "sha256": hashlib.sha256(child.read_bytes()).hexdigest()}
    write_payload_with_diff_ledger(root / "result.json", result)


if __name__ == "__main__":
    main()
