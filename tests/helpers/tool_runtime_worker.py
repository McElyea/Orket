"""Isolated tool-runtime native lifetime and deadline controls."""
from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

import psutil
import pytest

import orket
from orket.adapters.execution import owned_io
from orket.adapters.observability import log_publication
from orket.adapters.tools import runtime
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import bind_logging, prepare_logging, settle_log_write_frontier
from orket.settings import set_runtime_settings_context
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.helpers.sdk_observation_controls import public_caller, read_records
from tests.helpers.tool_runtime_controls import AsyncToolHold, arrange_tool, assert_outcome, entered, interrupt, settle


async def inspect_effect(root, route):
    records = await read_records(root / "orket.log")
    nominations = [row for row in records if row["event"] == "card_nomination"]
    timeouts = [row for row in records if row["event"] == "tool_timeout"]
    if route == "toolbox":
        assert len(nominations) == 1
        assert nominations[0]["data"]["issue_id"] == "retained-nomination"
    else:
        assert await asyncio.to_thread((root / "tool-effect.bin").read_bytes) == b"real tool effect"
    return {"native_effect_observed": True, "nomination_records": len(nominations), "timeout_records": len(timeouts)}


async def healthy_followup(root):
    def write(args, *, context):
        (root / "next-effect.bin").write_bytes(args["bytes"])
        return {"ok": True, "selected": context["selected"]}

    result = await runtime.ToolRuntimeExecutor().invoke(write, {"bytes": b"next tool"}, context={"selected": "next"})
    assert result == {"ok": True, "selected": "next"}
    assert await asyncio.to_thread((root / "next-effect.bin").read_bytes) == b"next tool"
    return True


async def observe(root, route, kind, stop, monkeypatch, observations):
    hold, operation, failure, value, args, context, name = await arrange_tool(root, route, kind, stop, monkeypatch)
    cause = failure.__cause__ if failure is not None else None
    native_context = failure.__context__ if failure is not None else None
    suppress_context = failure.__suppress_context__ if failure is not None else None
    active = asyncio.create_task(public_caller(operation))
    waiter = active
    try:
        await entered(hold)
        waiter = await interrupt(active, hold, stop)
        assert await sqlite_response(root / "responsive.sqlite3",
            lambda key, item: observations.append({"name": key, "value": item})) < .5
        await asyncio.sleep(.03)
        pending = not active.done() and not hold.finished.is_set()
        before = {"route": route, "kind": kind, "stop": stop, "invoke_pending": not active.done(),
            "tool_settled": hold.finished.is_set(), "caller_cancel_count": active.cancelling(),
            "external_waiter_done": waiter.done() if waiter is not active else None,
            "external_waiter_disposition": ("abandoned" if waiter.done() else "retained")
                if waiter is not active else None,
            "native_calls": hold.calls, "async_cancellations": len(hold.cancellations)
            if isinstance(hold, AsyncToolHold) else None}
        await asyncio.to_thread(write_payload_with_diff_ledger, root / "tool-before-release.json", before)
        hold.release.set()
        outcome = await asyncio.wait_for(active, 10)
        await settle(active, waiter, hold)
        await owned_io.run_owned_thread(settle_log_write_frontier, label="fixture-tool-log-frontier")
        physical = await inspect_effect(root, route)
        await asyncio.to_thread(write_payload_with_diff_ledger, root / "tool-after-settlement.json", {
            **before, **physical, "outcome_type": type(outcome).__name__, "tool_settled": hold.finished.is_set()})
        assert pending, "public invoke escaped while the admitted tool was still active"
        if stop == "abandoned-waiter":
            if before["external_waiter_done"]:
                assert waiter.cancelled(), "an abandoned external waiter must retain its cancellation"
            else:
                assert not waiter.cancelled(), "a retained wrapper should observe the captured invocation outcome"
                assert waiter.result() is outcome, "retained wrapper lost the exact invocation outcome"
        graph = assert_outcome(outcome, hold, failure, value, kind, stop, name, args, context, route)
        if failure is not None:
            assert failure.__cause__ is cause
            assert failure.__context__ is native_context and failure.__suppress_context__ is suppress_context
        assert physical["timeout_records"] == int(stop == "deadline" and failure is None)
        assert not getattr(hold, "expired", False)
        return {**before, **physical, **graph, "task_settled_before_emergency": active.done(),
                "tool_settled": hold.finished.is_set(), "healthy_followup": await healthy_followup(root),
                "external_waiter_terminal": ("cancelled" if waiter.cancelled() else "same_outcome")
                    if waiter is not active else None}
    finally:
        await settle(active, waiter, hold)


async def exercise(root, route, kind, stop):
    prepared = await prepare_logging(LoggingInputs(root, timezone_name="MST"))
    observations = []
    with pytest.MonkeyPatch.context() as monkeypatch, bind_logging(prepared):
        monkeypatch.setenv("ORKET_DURABLE_ROOT", str(root / ".orket/durable"))
        set_runtime_settings_context(user_settings={}, user_preferences={})
        result = await observe(root, route, kind, stop, monkeypatch, observations)
    assert log_publication._log_write_queue.qsize() == 0 and log_publication._log_writer_thread.is_alive()
    return {**result, "observations": observations, "logging_scope_explicit": True,
            "writer_shutdown": "process exit; no in-process stop"}


def main():
    root = Path(sys.argv[1]).resolve()
    result = asyncio.run(exercise(root, *sys.argv[2:]))
    process = psutil.Process()
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
        owner_origin=str(Path(owned_io.__file__).resolve()),
        owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest(),
        process_identity={"pid": process.pid, "create_time": process.create_time()},
        runtime_source={"path": str(Path(runtime.__file__).resolve()),
                        "sha256": hashlib.sha256(Path(runtime.__file__).read_bytes()).hexdigest()})
    write_payload_with_diff_ledger(root / "result.json", result)


if __name__ == "__main__":
    main()
