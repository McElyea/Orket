"""Isolated native fatal-handler control; an escaping fatal error fails this process."""
from __future__ import annotations

import asyncio
import hashlib
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

import orket
from orket import settings
from orket.adapters.execution import owned_io
from orket.application.services import api_runtime_preparation
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.failure_diagnostics import (
    DIAGNOSTIC_CONTEXT,
    PrimaryFailure,
    assert_note,
    assert_primary_graph,
    bind_handler,
    emergency_cleanup,
    enter_failed_api,
    observe_hold,
    prepare_failed_api,
    settle_handler,
)
from tests.helpers.runtime_cleanup_ports import NativeCleanupPort


async def warning(root, monkeypatch, fatal, record):
    hold = SimpleNamespace(entered=threading.Event(), release=threading.Event())
    port = await asyncio.to_thread(NativeCleanupPort, root / "native.sqlite3", failure=True, hold=hold)
    logger, handler = bind_handler(monkeypatch, owned_io, "logger", "Owned I/O failed while draining cancellation",
                                   fail=True, identity=root.name)
    handler.failure = fatal
    token = DIAGNOSTIC_CONTEXT.set("fatal-owner-context")
    active = asyncio.create_task(owned_io.run_owned_io(lambda: asyncio.to_thread(port.close),
                                label="fatal-handler-warning", preserve_failure=True))
    DIAGNOSTIC_CONTEXT.reset(token)
    try:
        assert await asyncio.to_thread(hold.entered.wait, 5)
        active.cancel("first caller interruption")
        hold.release.set()
        elapsed, before, outcome = await observe_hold(active, handler, root / "responsive.db", record)
        assert outcome is port.errors[0]
        assert_note(outcome, failed=True)
        assert_primary_graph(handler, outcome)
        assert elapsed < .5 and before["native_thread"] and not before["watchdog_expired"]
        assert not before["task_done"] and not before["done_after_cancellation"]
        assert before["context"] == "fatal-owner-context" and handler.calls == 1
        return {"primary_identity": True, "before": before, "handler_calls": handler.calls}
    finally:
        hold.release.set()
        await settle_handler(active, logger, handler)
        port.failure = False
        await asyncio.to_thread(port.close)
        record("fixture_cleanup", {"sqlite_closed": [await asyncio.to_thread(port.observe_closed)]})


async def preparation(root, monkeypatch, fatal, record):
    primary = PrimaryFailure("primary API construction failure")
    app, owners, ports = prepare_failed_api(root, monkeypatch, "completed", primary)
    logger, handler = bind_handler(monkeypatch, api_runtime_preparation, "LOGGER", "API ",
                                   fail=True, identity=root.name)
    handler.failure = fatal
    token = DIAGNOSTIC_CONTEXT.set("fatal-owner-context")
    active = asyncio.create_task(enter_failed_api(app))
    DIAGNOSTIC_CONTEXT.reset(token)
    try:
        elapsed, before, outcome = await observe_hold(active, handler, root / "responsive.db", record)
        assert outcome is primary
        assert_note(primary, failed=True)
        assert_primary_graph(handler, primary)
        states = await asyncio.gather(*(asyncio.to_thread(p.observe_closed) for p in ports))
        assert states == [True, True] and all(owner.engine._closed for owner in owners)
        assert elapsed < .5 and before["native_thread"] and not before["watchdog_expired"]
        assert not before["task_done"] and not before["done_after_cancellation"]
        assert before["context"] == "fatal-owner-context" and handler.calls == 1
        return {"primary_identity": True, "before": before, "closed_before_emergency": states}
    finally:
        await settle_handler(active, logger, handler)
        record("fixture_cleanup", await emergency_cleanup(owners, ports))


async def exercise(root, route, kind):
    observations = []
    fatal = SystemExit(57) if kind == "SystemExit" else KeyboardInterrupt("controlled fatal diagnostic")
    settings.set_settings_file(root / "settings/user_settings.json")
    settings.set_preferences_file(root / "settings/preferences.json")
    settings.set_runtime_settings_context(user_settings={}, user_preferences={})
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(settings, "ENV_FILE", root / "settings/.env")
        monkeypatch.setattr(settings, "_ENV_LOADED", True)
        monkeypatch.setenv("ORKET_DURABLE_ROOT", str(root / ".orket/durable"))
        result = await {"warning": warning, "preparation": preparation}[route](
            root, monkeypatch, fatal, lambda name, value: observations.append({"name": name, "value": value}))
    return {"route": route, "fatal_type": kind, "observations": observations, **result}


def main():
    root, route, kind = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3]
    result = asyncio.run(exercise(root, route, kind))
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
                  owner_origin=str(Path(owned_io.__file__).resolve()),
                  owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest())
    write_payload_with_diff_ledger(root / "result.json", result)


if __name__ == "__main__":
    main()
