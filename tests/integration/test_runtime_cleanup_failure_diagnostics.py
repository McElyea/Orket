"""Layer: integration. Actual nested runtime owners close peers after handler refusal."""
from __future__ import annotations

import asyncio
import json

import pytest

from orket.application.services import runtime_resource_cleanup
from tests.helpers.failure_diagnostics import (
    DIAGNOSTIC_CONTEXT,
    assert_note,
    assert_primary_graph,
    bind_handler,
    observe_hold,
    settle_handler,
)
from tests.helpers.runtime_cleanup_ports import (
    NativeCleanupPort,
    create_cleanup_runtime,
    exception_leaves,
    release_cleanup_runtime,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("kind", ["engine", "pipeline", "context"])
async def test_nested_runtime_cleanup_retains_handler_failure_and_closes_followers(
    tmp_path, monkeypatch, record_property, kind,
):
    monkeypatch.chdir(tmp_path)
    ports = [await asyncio.to_thread(NativeCleanupPort, tmp_path / f"native-{i}.sqlite3", failure=i == 0)
             for i in range(4)]
    runtime, owner = await create_cleanup_runtime(tmp_path, kind, ports)
    logger, handler = bind_handler(monkeypatch, runtime_resource_cleanup, "logger", "Runtime cleanup failed",
                                   fail=True, identity=tmp_path.name)
    token = DIAGNOSTIC_CONTEXT.set("runtime-owner-context")
    closing = asyncio.create_task(owner.close())
    DIAGNOSTIC_CONTEXT.reset(token)
    try:
        elapsed, before, outcome = await observe_hold(closing, handler, tmp_path / "responsive.db", record_property)
        states = await asyncio.gather(*(asyncio.to_thread(port.observe_closed) for port in ports))
        record_property("cleanup_observation", json.dumps({"attempts": [p.attempts for p in ports],
                        "closed": states, "handler_calls": handler.calls, **before}))
        # The engine's declared pipeline/context closes can retry the same failed
        # port. Preserve every native identity in their existing aggregate shape.
        leaves = exception_leaves(outcome)
        assert leaves == ports[0].errors and leaves
        for error in leaves:
            assert_note(error, failed=True)
            assert_primary_graph(handler, error)
        assert states == [False, True, True, True] and all(port.attempts >= 1 for port in ports)
        assert not getattr(owner, "_closed", False)
        assert elapsed < .5 and not before["task_done"] and not before["done_after_cancellation"]
        assert before["native_thread"] and not before["watchdog_expired"]
        assert before["context"] == "runtime-owner-context"
        assert all(error in handler.exceptions for error in leaves)
    finally:
        await settle_handler(closing, logger, handler)
        await release_cleanup_runtime(runtime, ports)
        closed = await asyncio.gather(*(asyncio.to_thread(port.observe_closed) for port in ports))
        record_property("fixture_cleanup", json.dumps({"sqlite_closed": closed}))
        assert all(closed)
