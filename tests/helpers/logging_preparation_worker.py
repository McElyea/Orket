"""Fresh-process integration control; the process owns its daemon through exit."""
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


async def guarded_prepare(inputs):
    try:
        return await logging_context.prepare_logging(inputs)
    except BaseException as failure:
        # Contain at the public caller, not an internal Task: a fatal Task escape
        # still aborts this native child and fails the parent's observed exit.
        return failure


async def arrange_interruption(active, stop):
    if stop == "cancel":
        active.cancel("first preparation interruption")
        await asyncio.sleep(0)
        active.cancel("second preparation interruption")
    if stop == "timeout":
        return asyncio.create_task(asyncio.wait_for(active, 0.02))
    return active


def observe_failure(inputs, hold, outcome):
    failure = hold.failure
    assert log_publication._log_writer_failure is failure
    if isinstance(failure, RuntimeError):
        assert type(outcome) is RuntimeError and str(outcome) == log_publication.LOG_WRITER_TERMINATED_ERROR
        assert outcome.__cause__ is failure
    else:
        assert outcome is failure
    assert not log_publication._log_prepared
    with pytest.raises(RuntimeError) as retry:
        logging_context.prepare_logging_native(inputs)
    assert str(retry.value) == log_publication.LOG_WRITER_TERMINATED_ERROR
    assert retry.value.__cause__ is failure and log_publication._log_writer_thread is hold.thread
    assert hold.calls == 1 and hold.real_starts == (1 if hold.phase == "after" else 0)
    return {"failure_identity": True, "retry_original_cause": True, "prepared": False,
            "writer_alive_at_return": hold.thread.is_alive(), "writer_ident": hold.thread.ident}


async def refuse_unbound_publication(root):
    before = (log_publication._log_write_queue.qsize(), log_publication.dropped_log_entry_count(),
              log_publication.event_subscriber_count())
    with pytest.raises(RuntimeError, match="^E_LOGGING_PREPARATION_REQUIRED$"):
        log_event("unprepared_must_not_publish", {}, root)
    assert before == (log_publication._log_write_queue.qsize(), log_publication.dropped_log_entry_count(),
                      log_publication.event_subscriber_count())
    assert not await asyncio.to_thread((root / "orket.log").exists)


async def observe_success(root, inputs, hold, outcome, stop):
    if stop == "none":
        assert type(outcome) is logging_context.PreparedLogging
    else:
        assert isinstance(outcome, asyncio.CancelledError), "caller interruption was lost"
    prepared = await logging_context.prepare_logging(inputs)
    assert log_publication._log_writer_thread is hold.thread and hold.calls == hold.real_starts == 1
    assert log_publication._log_prepared and hold.thread.is_alive()
    await refuse_unbound_publication(root)
    deliveries = []
    log_publication.subscribe_to_events(deliveries.append)
    try:
        with logging_context.bind_logging(prepared):
            log_event("prepared_native_control", {"observed": True}, Path("records"))
        assert logging_context.selected_logging(required=False) is None
        await owned_io.run_owned_thread(log_publication.settle_log_write_frontier, label="preparation-control-frontier")
    finally:
        log_publication.unsubscribe_from_events(deliveries.append)
    rows = json.loads((await asyncio.to_thread((root / "records/orket.log").read_text, encoding="utf-8")).strip())
    assert rows["event"] == "prepared_native_control" and len(deliveries) == 1
    assert log_publication.event_subscriber_count() == 0
    return {"prepared": True, "writer_alive_at_return": hold.thread.is_alive(), "writer_ident": hold.thread.ident,
            "record_written": True, "subscription_released": True, "context_restored": True}


async def exercise(root, phase, kind, stop):
    inputs, hold = LoggingInputs(root, queue_max=2), WriterStartHold(phase, kind)
    assert log_publication._log_writer_thread is None and not log_publication._log_prepared
    await refuse_unbound_publication(root)
    observations = []
    original_graph = None if hold.failure is None else (hold.failure.__cause__, hold.failure.__context__)
    with pytest.MonkeyPatch.context() as monkeypatch:
        hold.install(monkeypatch)
        active = asyncio.create_task(guarded_prepare(inputs))
        waiter = active
        try:
            assert await asyncio.to_thread(hold.entered.wait, 5), "real writer startup was not reached"
            waiter = await arrange_interruption(active, stop)
            elapsed = await sqlite_response(root / "responsive.sqlite3", lambda k, v: observations.append([k, v]))
            done, _ = await asyncio.wait({waiter}, timeout=0.1)
            assert not done and not active.done() and not hold.finished.is_set()
            assert active.cancelling() == {"none": 0, "cancel": 2, "timeout": 1}[stop]
            assert elapsed < 0.5 and hold.worker_ident != threading.get_ident() and not hold.expired
            hold.release.set()
            outcome = await asyncio.wait_for(waiter, 10)
            assert hold.finished.is_set() and not hold.expired
            if hold.failure is not None:
                result = await asyncio.to_thread(observe_failure, inputs, hold, outcome)
                assert (hold.failure.__cause__, hold.failure.__context__) == original_graph
                await refuse_unbound_publication(root)
            else:
                result = await observe_success(root, inputs, hold, outcome, stop)
            assert log_publication._log_writer_thread is hold.thread
            assert len([t for t in threading.enumerate() if t.name == "orket-log-writer"]) == int(hold.thread.is_alive())
            return {"phase": phase, "kind": kind, "stop": stop, "observations": observations,
                    "native_start_settled": True, "original_graph_preserved": True,
                    "start_calls": hold.calls, "real_starts": hold.real_starts,
                    "caller_cancel_requests": active.cancelling(), "watchdog_expired": hold.expired, **result}
        finally:
            hold.release.set()
            await asyncio.wait_for(asyncio.gather(active, waiter, return_exceptions=True), 10)


def main():
    root, phase, kind, stop = Path(sys.argv[1]).resolve(), *sys.argv[2:]
    result = asyncio.run(exercise(root, phase, kind, stop))
    process = psutil.Process()
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
                  owner_origin=str(Path(owned_io.__file__).resolve()),
                  owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest(),
                  publication_origin=str(Path(log_publication.__file__).resolve()),
                  publication_sha256=hashlib.sha256(Path(log_publication.__file__).read_bytes()).hexdigest(),
                  process_identity={"pid": process.pid, "create_time": process.create_time()},
                  writer_shutdown="process-exit; no in-process stop or join is claimed")
    write_payload_with_diff_ledger(root / "result.json", result)


if __name__ == "__main__":
    main()
