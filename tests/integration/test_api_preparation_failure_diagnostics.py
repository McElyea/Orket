"""Layer: integration. Acquired real API graph/SQLite resources survive diagnostic failure."""
from __future__ import annotations

import asyncio
import json

import pytest

from orket.application.services import api_runtime_preparation
from tests.helpers.failure_diagnostics import (
    DIAGNOSTIC_CONTEXT,
    PrimaryFailure,
    assert_note,
    assert_primary_graph,
    bind_handler,
    emergency_cleanup,
    enter_failed_api,
    failure_tree,
    observe_hold,
    prepare_failed_api,
    settle_handler,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("phase", ["partial", "completed"])
@pytest.mark.parametrize("handler_fails", [False, True])
async def test_preparation_keeps_primary_and_attempts_all_acquired_cleanup(
    tmp_path, monkeypatch, record_property, phase, handler_fails,
):
    primary = PrimaryFailure("controlled construction-policy refusal")
    app, owners, ports = prepare_failed_api(tmp_path, monkeypatch, phase, primary)
    logger, handler = bind_handler(monkeypatch, api_runtime_preparation, "LOGGER", "API ",
                                   fail=handler_fails, identity=tmp_path.name)
    token = DIAGNOSTIC_CONTEXT.set("preparation-owner-context")
    task = asyncio.create_task(enter_failed_api(app))
    DIAGNOSTIC_CONTEXT.reset(token)
    try:
        elapsed, before, outcome = await observe_hold(task, handler, tmp_path / "responsive.db", record_property)
        states = await asyncio.gather(*(asyncio.to_thread(port.observe_closed) for port in ports))
        record_property("cleanup_observation", json.dumps({"attempts": [p.attempts for p in ports], "closed": states,
                        "engine_closed": [owner.engine._closed for owner in owners], **before}))
        assert primary in failure_tree(outcome)
        assert_note(primary, failed=handler_fails)
        assert_primary_graph(handler, primary)
        assert len(ports) == 2 and all(port.attempts >= 1 for port in ports)
        assert states == ([True, False] if phase == "partial" else [True, True])
        assert owners and all(owner.engine._closed for owner in owners)
        if phase == "partial":
            assert ports[1].errors[0] in failure_tree(outcome)
            assert_note(ports[1].errors[0], failed=handler_fails)
            assert_primary_graph(handler, ports[1].errors[0])
        assert elapsed < .5 and not before["task_done"] and before["native_thread"]
        assert not before["done_after_cancellation"] and primary in handler.exceptions
        assert not before["watchdog_expired"] and before["context"] == "preparation-owner-context"
        assert not getattr(app.state, "api_ready", False)
    finally:
        await settle_handler(task, logger, handler)
        record_property("fixture_cleanup", json.dumps(await emergency_cleanup(owners, ports)))
