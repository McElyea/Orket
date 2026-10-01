"""Actual shared writer with concurrent application values and refusing loop hooks."""
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
from orket.logging import log_event
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.logging_preparation_start import WriterStartHold
from tests.helpers.runtime_verification_hold import sqlite_response


async def prepared_peers(root):
    inputs = [LoggingInputs(root / "first", timezone_name="MST", queue_max=32),
              LoggingInputs(root / "second", timezone_name="UTC", missing_workspace_mode="fail_fast", queue_max=32)]
    hold = WriterStartHold("before", "success")
    observations = []
    with pytest.MonkeyPatch.context() as monkeypatch:
        hold.install(monkeypatch)
        first = asyncio.create_task(logging_context.prepare_logging(inputs[0]))
        peers = []
        try:
            assert await asyncio.to_thread(hold.entered.wait, 5)
            peers = [asyncio.create_task(logging_context.prepare_logging(inputs[1])),
                     asyncio.create_task(logging_context.prepare_logging(LoggingInputs(root, queue_max=64)))]
            await asyncio.sleep(0.02)
            assert not first.done() and all(not task.done() for task in peers)
            assert await sqlite_response(root / "concurrent.sqlite3", lambda k, v: observations.append([k, v])) < 0.5
            hold.release.set()
            values = await asyncio.gather(first, *peers, return_exceptions=True)
            assert type(values[0]) is type(values[1]) is logging_context.PreparedLogging
            assert type(values[2]) is RuntimeError and str(values[2]) == "E_LOGGING_QUEUE_CONFIGURATION_CONFLICT"
            assert hold.calls == hold.real_starts == 1 and hold.finished.is_set() and not hold.expired
            assert log_publication._log_write_queue.maxsize == 32 and log_publication._log_writer_thread is hold.thread
            return values[:2], observations
        finally:
            hold.release.set()
            await asyncio.wait_for(asyncio.gather(first, *peers, return_exceptions=True), 10)


def loop_forbidden(original):
    def guarded(*args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return original(*args, **kwargs)
        raise AssertionError("optional admission attempted native preparation on the loop")
    return guarded


async def interleave_publication(prepared, other, name):
    with logging_context.bind_logging(prepared):
        log_event(name, {"position": 1}, Path("records"))
        await asyncio.sleep(0)
        with logging_context.bind_logging(other):
            assert logging_context.selected_logging() is other
        assert logging_context.selected_logging() is prepared
        log_event(name, {"position": 2}, Path("records"))
    assert logging_context.selected_logging(required=False) is None


async def exercise(root):
    # Initialization refusals cannot consume the first configuration or writer attempt.
    with pytest.raises(ValueError, match="E_LOGGING_INVOCATION_ROOT_ABSOLUTE_REQUIRED"):
        LoggingInputs(Path("relative"))
    with pytest.raises(ValueError, match="E_LOGGING_PREPARATION_INPUT_UNSUPPORTED"):
        LoggingInputs(root, queue_max=True)
    with pytest.raises(RuntimeError, match="E_LOGGING_PREPARATION_REQUIRES_NATIVE_CONTEXT"):
        logging_context.prepare_logging_native(LoggingInputs(root))
    with pytest.raises(RuntimeError, match="E_LOGGING_PREPARATION_REQUIRED"):
        log_event("unprepared", {}, root)
    assert log_publication._log_writer_thread is None and not log_publication._log_queue_configured
    prepared, observations = await prepared_peers(root)
    writer = log_publication._log_writer_thread
    with pytest.MonkeyPatch.context() as monkeypatch:
        original_cwd = Path.cwd
        monkeypatch.setattr(Path, "cwd", classmethod(lambda _cls: loop_forbidden(original_cwd)()))
        monkeypatch.setattr(threading.Thread, "start", loop_forbidden(threading.Thread.start))
        monkeypatch.setenv("ORKET_TIMEZONE", "Asia/Tokyo")
        monkeypatch.setenv("ORKET_LOG_QUEUE_MAX", "1")
        monkeypatch.setenv("ORKET_LOGGING_MISSING_CONTEXT_MODE", "legacy_default")
        await asyncio.gather(interleave_publication(prepared[0], prepared[1], "first"),
                             interleave_publication(prepared[1], prepared[0], "second"))
        with logging_context.bind_logging(prepared[1]), pytest.raises(RuntimeError, match="E_LOG_WORKSPACE_REQUIRED"):
            log_event("missing_must_refuse", {})
        with logging_context.bind_logging(prepared[0]):
            log_event("legacy_default", {})
        await owned_io.run_owned_thread(log_publication.settle_log_write_frontier, label="context-control-frontier")
    assert log_publication._log_writer_thread is writer and writer.is_alive()
    assert log_publication._log_write_queue.maxsize == 32
    assert logging_context.selected_logging(required=False) is None
    return {"observations": observations, "one_writer": True, "configuration_refused": True,
            "zero_effect_initial_refusals": True, "loop_native_hooks_absent": True, "context_restored": True}


def main():
    root = Path(sys.argv[1]).resolve()
    result = asyncio.run(exercise(root))
    for name, offset in (("first", "-07:00"), ("second", "+00:00")):
        records = [json.loads(row) for row in (root / name / "records/orket.log").read_text().splitlines()]
        assert [row["data"]["position"] for row in records] == [1, 2]
        assert all(row["event"] == name and row["timestamp"].endswith(offset) for row in records)
    default = json.loads((root / "first/workspace/default/orket.log").read_text().strip())
    assert default["event"] == "legacy_default" and default["data"]["logging_context_marker"] == "workspace_default_fallback"
    assert not (root / "second/workspace/default/orket.log").exists()
    process = psutil.Process()
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
                  owner_origin=str(Path(owned_io.__file__).resolve()),
                  owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest(),
                  process_identity={"pid": process.pid, "create_time": process.create_time()},
                  exact_physical_records=True, writer_alive_at_return=log_publication._log_writer_thread.is_alive())
    write_payload_with_diff_ledger(root / "result.json", result)


if __name__ == "__main__":
    main()
