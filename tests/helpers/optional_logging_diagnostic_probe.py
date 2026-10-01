"""Isolated diagnostic-write refusal with actual daemon, files and handoff tokens."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from pathlib import Path

import psutil

from orket import logging as logging_api
from orket.adapters.observability import log_publication as owner
from orket.adapters.observability.logging_context import bind_logging, prepare_logging_native
from orket.core.contracts.logging_inputs import LoggingInputs
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

__test__ = False


def _install_refusals(kind: str, failure: BaseException, attempts: list[str]):
    original_append, original_clock = owner._append_line_sync, logging_api.now_local
    samples = 0

    def append(path, line):
        event = json.loads(line)["event"]
        attempts.append(event)
        if event == "logging_subscriber_failed" and kind not in {"handler-oserror", "clock-oserror"}:
            raise failure
        original_append(path, line)

    def clock(timezone=None):
        nonlocal samples
        samples += 1
        if kind == "clock-oserror" and samples == 2:
            raise failure
        return original_clock(timezone)

    class DiagnosticHandler(logging.Handler):
        def emit(self, record):
            if kind == "handler-oserror" and record.getMessage() == "logging_subscriber_failed":
                raise failure

    owner._append_line_sync, logging_api.now_local = append, clock
    handler = DiagnosticHandler()
    logging.getLogger("orket").addHandler(handler)
    return original_append, original_clock, handler


async def _optional(root: Path, event: str, prepared) -> None:
    with bind_logging(prepared):
        logging_api.log_event(event, {}, workspace=root)


def _settle(failure: BaseException) -> dict:
    try:
        owner.settle_log_write_frontier()
    except RuntimeError as exc:
        return {"result": "failure", "error": str(exc), "cause_type": type(exc.__cause__).__name__,
                "cause_identity": exc.__cause__ is failure}
    return {"result": "success"}


def observe(root: Path, kind: str) -> dict:
    owner.settle_log_write_frontier()
    prepared = prepare_logging_native(LoggingInputs(root))
    failure = (ValueError if kind == "append-valueerror" else OSError)("diagnostic refusal fixture")
    attempts, delivered, thread_errors = [], [], []
    original_append, original_clock, handler = _install_refusals(kind, failure, attempts)
    original_hook = threading.excepthook
    threading.excepthook = lambda args: thread_errors.append(type(args.exc_value).__name__)

    def first(record, acknowledge):
        if record["event"] == "diagnostic_probe":
            raise ValueError("subscriber refusal fixture")
        acknowledge()

    def second(record, acknowledge):
        delivered.append(record["event"])
        acknowledge()

    subscriptions = [owner.subscribe_to_event_handoffs(first), owner.subscribe_to_event_handoffs(second)]
    outward = {"result": "success"}
    try:
        try:
            if kind == "native-oserror":
                logging_api.log_event("diagnostic_probe", {}, workspace=root)
            else:
                asyncio.run(_optional(root, "diagnostic_probe", prepared))
        except OSError as exc:
            outward = {"result": "failure", "type": type(exc).__name__, "identity": exc is failure}
        frontier = _settle(failure)
        if frontier["result"] == "success" and kind != "native-oserror":
            asyncio.run(_optional(root, "later_optional", prepared))
            later_frontier = _settle(failure)
        else:
            later_frontier = None
        for subscription in subscriptions:
            owner.settle_event_subscription(subscription)
        if owner._log_writer_failure is not None:
            owner._log_writer_thread.join(3)
        return dict(kind=kind, outward=outward, frontier=frontier, later_frontier=later_frontier,
                    delivered=delivered, attempts=attempts, pending=[item.pending for item in subscriptions],
                    states=[item.state for item in subscriptions], writer_alive=owner._log_writer_thread.is_alive(),
                    retained_identity=owner._log_writer_failure is failure, thread_errors=thread_errors,
                    records=[json.loads(line)["event"] for line in (root / "orket.log").read_text().splitlines()],
                    logging_origin=str(Path(logging_api.__file__).resolve()), pid=os.getpid(),
                    create_time=psutil.Process().create_time())
    finally:
        owner._append_line_sync, logging_api.now_local = original_append, original_clock
        threading.excepthook = original_hook
        logging.getLogger("orket").removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    print(json.dumps(write_payload_with_diff_ledger(root / "probe-report.json", observe(root, sys.argv[2]))))
