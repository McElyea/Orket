"""Isolated real-daemon failure with queued, undelivered registration tokens."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

import psutil

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.observability import log_publication as owner
from orket.logging import log_event, settle_log_write_frontier
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.logging_async_opening import sqlite_observation

__test__ = False
LOGGING_ORIGIN = str(Path(owner.__file__).resolve())
PROCESS_IDENTITY = {"pid": os.getpid(), "create_time": psutil.Process().create_time()}


async def observe(root: Path, kind: str) -> dict:
    entered, release = threading.Event(), threading.Event()
    failure = (ValueError if kind == "handler-value" else OSError)("optional native fatal fixture")
    callbacks, thread_errors = [], []
    original_parent = owner._ensure_log_parent

    def fail_preparation(path):
        if kind == "prepare-oserror" and path == root / "orket.log":
            raise failure
        original_parent(path)

    owner._ensure_log_parent = fail_preparation

    class Fatal(logging.Handler):
        def emit(self, record):
            if record.getMessage() == "optional_fatal":
                entered.set()
                assert release.wait(5), "fatal fixture release missing"
                if kind != "prepare-oserror":
                    raise failure

    def callback(record, acknowledge):
        callbacks.append(record)
        acknowledge()

    handler, logger = Fatal(), logging.getLogger("orket")
    logger.addHandler(handler)
    subscription = owner.subscribe_to_event_handoffs(callback)
    original_hook = threading.excepthook
    threading.excepthook = lambda value: thread_errors.append(type(value.exc_value).__name__)
    drain = None
    try:
        log_event("optional_fatal", {}, workspace=root)
        assert await asyncio.to_thread(entered.wait, 3)
        log_event("stranded", {}, workspace=root)
        pending_before = subscription.pending
        owner.begin_event_subscription_drain(subscription)
        drain = asyncio.create_task(run_owned_thread(
            lambda: owner.settle_event_subscription(subscription), label="fatal-registration-drain"))
        sqlite = await sqlite_observation(root / "independent.sqlite3", time.perf_counter())
        pending_during_hold = not drain.done()
        release.set()
        try:
            await run_owned_thread(settle_log_write_frontier, label="fatal-frontier")
        except RuntimeError as exc:
            frontier = {"error": str(exc), "cause_type": type(exc.__cause__).__name__,
                        "cause_identity": exc.__cause__ is failure}
        else:
            frontier = {"error": None}
        await drain
        writer = owner._log_writer_thread
        await run_owned_thread(lambda: writer.join(3), label="fatal-writer-join")
        log_event("after_death", {}, workspace=root)
        return dict(kind=kind, pending_before=pending_before, pending_during_hold=pending_during_hold,
                    pending_after=subscription.pending, state=subscription.state, callbacks=callbacks,
                    frontier=frontier, retained_identity=owner._log_writer_failure is failure,
                    writer_alive=writer.is_alive(), same_writer=writer is owner._log_writer_thread,
                    thread_errors=thread_errors, sqlite=sqlite, **PROCESS_IDENTITY, logging_origin=LOGGING_ORIGIN)
    finally:
        release.set()
        if drain is not None:
            await drain
        logger.removeHandler(handler)
        handler.close()
        threading.excepthook = original_hook
        owner._ensure_log_parent = original_parent


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    result = asyncio.run(observe(root, sys.argv[2]))
    persisted = write_payload_with_diff_ledger(root / "probe-report.json", result)
    print(json.dumps(persisted, sort_keys=True))
