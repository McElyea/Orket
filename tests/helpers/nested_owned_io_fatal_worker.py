"""Isolated nested owner control; only the public caller may catch the fatal failure."""
from __future__ import annotations

import asyncio
import hashlib
import sqlite3
import sys
import threading
from pathlib import Path

import orket
from orket.adapters.execution import owned_io
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.runtime_cleanup_ports import NativeCleanupPort
from tests.helpers.runtime_verification_hold import sqlite_response


class HeldNativeFailure:
    def __init__(self, port, fatal):
        self.port, self.fatal = port, fatal
        self.entered, self.release, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.calls, self.thread, self.expired = 0, None, False

    def run(self):
        self.calls += 1
        self.thread = threading.get_ident()
        try:
            self.port.connection.execute("INSERT INTO cleanup_marker VALUES (17)")
            self.port.connection.commit()
            self.entered.set()
            self.expired = not self.release.wait(5)
            assert not self.expired, "nested native fixture was not released"
            raise self.fatal
        finally:
            self.finished.set()


async def nested_operation(depth, operation):
    if depth == 0:
        return await owned_io.run_owned_thread(operation, label="nested-native-leaf")
    return await owned_io.run_owned_io(lambda: nested_operation(depth - 1, operation),
                                      label=f"nested-async-owner-{depth}", preserve_failure=True)


async def public_caller(depth, native, port):
    try:
        await nested_operation(depth, native.run)
    except BaseException as failure:
        return failure
    finally:
        await asyncio.to_thread(port.close)


async def arrange_interruption(active, stop):
    if stop == "cancel":
        active.cancel("first nested caller cancellation")
        await asyncio.sleep(0)
        active.cancel("second nested caller cancellation")
    if stop == "timeout":
        return asyncio.create_task(asyncio.wait_for(active, 0.02))
    return active


def retained_marker(database):
    with sqlite3.connect(database) as connection:
        return connection.execute("SELECT value FROM cleanup_marker").fetchall()


async def observe(root, depth, stop, port, native, record):
    fatal = native.fatal
    original_cause, original_context = fatal.__cause__, fatal.__context__
    active = asyncio.create_task(public_caller(depth, native, port))
    waiter = active
    try:
        assert await asyncio.to_thread(native.entered.wait, 5), "native write was not reached"
        waiter = await arrange_interruption(active, stop)
        assert await sqlite_response(root / "responsive.sqlite3", record) < 0.5
        done, _ = await asyncio.wait({waiter}, timeout=0.1)
        assert not done and not active.done(), "outer owner escaped before native settlement"
        assert active.cancelling() == {"none": 0, "cancel": 2, "timeout": 1}[stop]
        assert not port.closed and not native.finished.is_set()
        assert native.thread != threading.get_ident() and not native.expired
        native.release.set()
        outcome = await asyncio.wait_for(waiter, 10)
        assert outcome is fatal and outcome.__cause__ is original_cause and outcome.__context__ is original_context
        assert native.calls == 1 and native.finished.is_set() and not native.expired
        assert await asyncio.to_thread(port.observe_closed)
        assert await asyncio.to_thread(retained_marker, root / "retained.sqlite3") == [(17,)]
        assert await sqlite_response(root / "sibling-after.sqlite3", record) < 0.5
        assert await nested_operation(depth, lambda: "healthy-next-operation") == "healthy-next-operation"
        return {"failure_identity": True, "cause_identity": True, "context_identity": True,
                "failure_type": type(outcome).__name__, "failure_args": list(outcome.args),
                "caller_cancel_requests": active.cancelling(), "native_calls": native.calls,
                "native_thread": True, "native_finished": True, "watchdog_expired": native.expired,
                "sqlite_closed_before_emergency": True, "retained_marker": [17],
                "sibling_continued": True, "healthy_next_operation": True}
    finally:
        native.release.set()
        try:
            await asyncio.wait_for(asyncio.gather(active, waiter, return_exceptions=True), 10)
        finally:
            await asyncio.to_thread(port.close)


async def exercise(root, kind, stop, depth):
    fatal = SystemExit(57) if kind == "SystemExit" else KeyboardInterrupt("nested native interruption")
    fatal.__cause__, fatal.__context__ = RuntimeError("retained cause"), LookupError("retained context")
    observations = []

    def record(name, value):
        observations.append({"name": name, "value": value})

    port = await asyncio.to_thread(NativeCleanupPort, root / "retained.sqlite3")
    native = HeldNativeFailure(port, fatal)
    try:
        result = await observe(root, depth, stop, port, native, record)
    finally:
        native.release.set()
        await asyncio.to_thread(port.close)
        record("fixture_cleanup", {"sqlite_closed": await asyncio.to_thread(port.observe_closed),
                                    "native_finished": native.finished.is_set()})
    return {"fatal_type": kind, "stop": stop, "depth": depth, "observations": observations, **result}


def main():
    root, kind, stop, depth = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3], int(sys.argv[4])
    result = asyncio.run(exercise(root, kind, stop, depth))
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
                  owner_origin=str(Path(owned_io.__file__).resolve()),
                  owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest())
    write_payload_with_diff_ledger(root / "result.json", result)


if __name__ == "__main__":
    main()
