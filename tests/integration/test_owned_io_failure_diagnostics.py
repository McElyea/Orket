"""Layer: integration. Real native SQLite failure and retained cancellation diagnostics."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from types import SimpleNamespace

import pytest

from orket.adapters.execution import owned_io
from tests.helpers.failure_diagnostics import (
    DIAGNOSTIC_CONTEXT,
    assert_note,
    assert_primary_graph,
    bind_handler,
    observe_hold,
    settle_handler,
)
from tests.helpers.runtime_cleanup_ports import NativeCleanupPort

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("preserve,handler_fails,replace_logger", [
    (False, False, False), (True, False, False), (False, True, False), (True, True, False),
    (True, True, True),
])
async def test_cancelled_native_failure_retains_diagnostic_and_selected_outcome(
    tmp_path, monkeypatch, record_property, preserve, handler_fails, replace_logger,
):
    native = SimpleNamespace(entered=threading.Event(), release=threading.Event())
    port = await asyncio.to_thread(NativeCleanupPort, tmp_path / "native.sqlite3", failure=True, hold=native)
    logger, handler = bind_handler(monkeypatch, owned_io, "logger", "Owned I/O failed while draining cancellation",
                                   fail=handler_fails, identity=tmp_path.name)
    token = DIAGNOSTIC_CONTEXT.set("native-owner-context")
    task = asyncio.create_task(owned_io.run_owned_io(lambda: asyncio.to_thread(port.close),
                              label="native-failure-control", preserve_failure=preserve))
    DIAGNOSTIC_CONTEXT.reset(token)
    try:
        assert await asyncio.to_thread(native.entered.wait, 5)
        # Capture is invocation-scoped, not a late lookup after the first worker.
        if replace_logger:
            monkeypatch.setattr(owned_io, "logger", logging.getLogger("tests.failure.late-replacement"))
        task.cancel("original interruption")
        native.release.set()
        elapsed, before, outcome = await observe_hold(task, handler, tmp_path / "responsive.db", record_property)
        record_property("diagnostic_observation", json.dumps({**before, "calls": handler.calls,
                        "outcome_type": type(outcome).__name__, "native_errors": len(port.errors)}))
        assert len(port.errors) == 1
        if preserve:
            assert outcome is port.errors[0]
        else:
            assert type(outcome) is asyncio.CancelledError and outcome.args == ("original interruption",)
        assert_note(outcome, failed=handler_fails)
        assert elapsed < .5 and before == {"task_done": False, "native_thread": True,
                                          "watchdog_expired": False, "context": "native-owner-context",
                                          "done_after_cancellation": False}
        assert handler.calls == 1 and handler.finished.is_set()
        assert handler.exceptions == [port.errors[0]]
        assert_primary_graph(handler, port.errors[0])
    finally:
        native.release.set()
        await settle_handler(task, logger, handler)
        port.failure = False
        await asyncio.to_thread(port.close)
        closed = await asyncio.to_thread(port.observe_closed)
        record_property("fixture_cleanup", json.dumps({"sqlite_closed": [closed]}))
        assert closed
