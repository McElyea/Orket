"""Layer: integration. Real API lifespan/resources retain failed supporting diagnostics."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from orket.application.services import application_runtime_lifetime
from tests.helpers.failure_diagnostics import (
    DIAGNOSTIC_CONTEXT,
    assert_note,
    assert_primary_graph,
    bind_handler,
    finish_api,
    observe_hold,
    prepare_running_api,
    settle_handler,
    stage_api_failure,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
PREFIX = {"resource": "Application-owned resource teardown failed",
          "final": "API final resource teardown failed",
          "background": "Application background task failed",
          "tracked": "Application owned task failed during teardown"}


@pytest.mark.parametrize("kind", ["resource", "final", "background", "tracked"])
@pytest.mark.parametrize("handler_fails", [False, True])
async def test_api_close_retains_diagnostics_and_all_declared_resource_attempts(
    tmp_path, monkeypatch, record_property, kind, handler_fails,
):
    state = await prepare_running_api(tmp_path, monkeypatch)
    logger, handler = bind_handler(monkeypatch, application_runtime_lifetime, "LOGGER", PREFIX[kind],
                                   fail=handler_fails, identity=tmp_path.name)
    loop, callbacks = asyncio.get_running_loop(), []
    previous = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, details: callbacks.append(details))
    closing = None
    token = DIAGNOSTIC_CONTEXT.set("lifetime-owner-context")
    try:
        primary = await stage_api_failure(state, kind, monkeypatch, tmp_path)
        admission = None
        if kind == "background":
            assert await asyncio.to_thread(handler.entered.wait, 5)
            admission = {"background_done": state.background.done(), "accepting": state.owner.accepting_work,
                         "primary_recorded": state.owner._background_failure is primary}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(state.app), base_url="http://test") as client:
                admission["health_status"] = (await client.get("/health")).status_code
        closing = asyncio.create_task(state.owner.close())
        DIAGNOSTIC_CONTEXT.reset(token)
        token = None
        inspect_order = (lambda: {"background_done": state.background.done(),
            "port_attempts": [p.attempts for p in state.ports],
            "final_close_entries": len(state.final_close_entries)}) if kind == "background" else None
        elapsed, before, outcome = await observe_hold(closing, handler, tmp_path / "responsive.db", record_property,
                                                     before_release=inspect_order)
        states = await asyncio.gather(*(asyncio.to_thread(port.observe_closed) for port in state.ports))
        record_property("cleanup_observation", json.dumps({"attempts": [p.attempts for p in state.ports],
            "closed": states, "engine_closed": state.owner.engine._closed, "admission": admission,
            "callback_errors": len(callbacks), **before}))
        primary = primary or state.ports[-1].errors[0]
        assert isinstance(outcome, RuntimeError) and outcome.__cause__ is primary
        assert str(outcome) == "API runtime teardown failed for 1 owner(s)."
        assert_note(primary, failed=handler_fails)
        assert_primary_graph(handler, primary)
        assert states == ([True, False] if kind == "resource" else [True, True, False] if kind == "final" else [True, True])
        assert all(port.attempts >= 1 for port in state.ports) and state.owner.engine._closed
        assert not state.owner.closed and not state.owner.accepting_work
        assert state.owner.active_background_task_count == state.owner.active_request_count == 0
        assert elapsed < .5 and not before["task_done"] and not before["done_after_cancellation"]
        assert before["native_thread"] and not before["watchdog_expired"]
        assert before["context"] == "lifetime-owner-context" and primary in handler.exceptions and not callbacks
        if kind == "background":
            assert admission == {"background_done": False, "accepting": False, "primary_recorded": True,
                                 "health_status": 503}
            assert before["resource_order"] == {"background_done": False, "port_attempts": [0, 0],
                                                "final_close_entries": 0}
    finally:
        if token is not None:
            DIAGNOSTIC_CONTEXT.reset(token)
        if closing is None:
            closing = asyncio.create_task(state.owner.close())
        await settle_handler(closing, logger, handler)
        loop.set_exception_handler(previous)
        record_property("fixture_cleanup", json.dumps(await finish_api(state)))
