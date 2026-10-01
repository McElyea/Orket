"""Isolated API publication; an inner fatal Task escape fails the native child."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import threading
from pathlib import Path

import pytest

import orket
from orket import settings
from orket.adapters.execution import owned_io
from orket.adapters.observability import log_publication
from orket.application.services.api_event_service import ApiEventService
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.failure_diagnostics import DIAGNOSTIC_CONTEXT, bind_handler
from tests.helpers.runtime_cleanup_ports import NativeCleanupPort
from tests.helpers.runtime_verification_hold import sqlite_response

EVENT = "native_fatal_publication"
RECOVERY_EVENT = "native_publication_after_fatal"


async def guarded_publication(service, port):
    # Catch at the public caller boundary inside this task. The product must not
    # raise through a different, internal Task and abort the event-loop runner.
    try:
        await service.emit(EVENT, {"source": "native-fatal-owner-control"})
    except BaseException as failure:
        return failure
    finally:
        await asyncio.to_thread(port.close)


async def arrange_interruption(active, stop):
    if stop == "cancel":
        active.cancel("first native publication cancellation")
        await asyncio.sleep(0)
        active.cancel("second native publication cancellation")
    if stop == "timeout":
        return asyncio.create_task(asyncio.wait_for(active, 0.02))
    return active


async def observe_publication(root, service, port, handler, fatal, stop, record):
    original_cause, original_context = fatal.__cause__, fatal.__context__
    token = DIAGNOSTIC_CONTEXT.set("native-fatal-publication-context")
    active = asyncio.create_task(guarded_publication(service, port))
    DIAGNOSTIC_CONTEXT.reset(token)
    waiter = active
    try:
        assert await asyncio.to_thread(handler.entered.wait, 5), "native handler was not reached"
        waiter = await arrange_interruption(active, stop)
        elapsed = await sqlite_response(root / "responsive.sqlite3", record)
        done, _ = await asyncio.wait({waiter}, timeout=0.1)
        assert not done and not active.done(), "publication escaped before native settlement"
        expected_requests = {"none": 0, "cancel": 2, "timeout": 1}[stop]
        assert active.cancelling() == expected_requests, "requested interruption was not observed"
        assert not port.closed and not handler.finished.is_set()
        assert elapsed < 0.5 and handler.thread != threading.get_ident() and not handler.expired
        assert handler.context == "native-fatal-publication-context"
        handler.unblock.set()
        outcome = await asyncio.wait_for(waiter, 10)
        assert outcome is fatal and outcome.__cause__ is original_cause and outcome.__context__ is original_context
        assert handler.calls == 1 and handler.finished.is_set() and not handler.expired
        assert await asyncio.to_thread(port.observe_closed)
        assert await sqlite_response(root / "sibling-after.sqlite3", record) < 0.5
        await service.emit(RECOVERY_EVENT, {"continued": True})
        rows = (await asyncio.to_thread((root / "orket.log").read_text, encoding="utf-8")).splitlines()
        events = [json.loads(row)["event"] for row in rows]
        assert RECOVERY_EVENT in events and EVENT not in events
        return {"failure_identity": True, "cause_identity": True, "context_identity": True,
                "failure_type": type(outcome).__name__, "failure_args": list(outcome.args),
                "handler_calls": handler.calls, "native_thread": True, "native_finished": True,
                "watchdog_expired": handler.expired, "caller_cancel_requests": active.cancelling(),
                "sqlite_closed_before_emergency": True, "sibling_continued": True,
                "recovery_event_written": True, "failed_event_written": False}
    finally:
        handler.unblock.set()
        try:
            await asyncio.wait_for(asyncio.gather(active, waiter, return_exceptions=True), 10)
        finally:
            await asyncio.to_thread(port.close)


async def exercise(root, kind, stop):
    settings.set_settings_file(root / "settings/user_settings.json")
    settings.set_preferences_file(root / "settings/preferences.json")
    settings.set_runtime_settings_context(user_settings={}, user_preferences={})
    fatal = SystemExit(57) if kind == "SystemExit" else KeyboardInterrupt("native publication interrupted")
    fatal.__cause__ = RuntimeError("retained native cause")
    fatal.__context__ = LookupError("retained native context")
    observations = []

    def record(name, value):
        observations.append({"name": name, "value": value})

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(settings, "ENV_FILE", root / "settings/.env")
        monkeypatch.setattr(settings, "_ENV_LOADED", True)
        monkeypatch.setenv("ORKET_DURABLE_ROOT", str(root / ".orket/durable"))
        service = await asyncio.to_thread(ApiEventService, root)
        port = await asyncio.to_thread(NativeCleanupPort, root / "owned-resource.sqlite3")
        logger, handler = bind_handler(monkeypatch, log_publication, "_logger", EVENT,
                                       fail=True, identity=root.name)
        handler.failure = fatal
        try:
            result = await observe_publication(root, service, port, handler, fatal, stop, record)
        finally:
            handler.unblock.set()
            logger.removeHandler(handler)
            handler.close()
            await asyncio.to_thread(port.close)
            record("fixture_cleanup", {"sqlite_closed": await asyncio.to_thread(port.observe_closed),
                                        "native_finished": handler.finished.is_set()})
    return {"fatal_type": kind, "stop": stop, "observations": observations, **result}


def main():
    root, kind, stop = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3]
    result = asyncio.run(exercise(root, kind, stop))
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
                  owner_origin=str(Path(owned_io.__file__).resolve()),
                  owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest())
    write_payload_with_diff_ledger(root / "result.json", result)


if __name__ == "__main__":
    main()
