"""Layer: integration. Real startup diagnostics retain the API owner and SQLite progress."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from types import SimpleNamespace

import httpx
import pytest

from orket.application.services import api_startup_service
from orket.application.services.api_authentication_service import ApiAuthenticationService
from tests.helpers.api_startup_diagnostic import (
    STARTUP_CONTEXT,
    assert_closed,
    enter_api,
    prepare_app,
    settle_api,
)
from tests.helpers.runtime_verification_hold import sqlite_response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("warning", ["bypass", "tls"])
@pytest.mark.parametrize("outcome", ["success", "cancel", "failure", "cancel_failure"])
async def test_startup_handler_retains_native_owner(tmp_path, monkeypatch, record_property, warning, outcome):
    failure = OSError("controlled startup diagnostic failure") if "failure" in outcome else None
    probe = prepare_app(tmp_path, monkeypatch, warning=warning, failure=failure)
    token = STARTUP_CONTEXT.set("captured-startup-context")
    task = asyncio.create_task(enter_api(probe))
    STARTUP_CONTEXT.reset(token)
    try:
        assert await asyncio.to_thread(probe.handler.entered.wait, 10)
        elapsed = await sqlite_response(tmp_path / "responsive.db", record_property, probe.handler.started)
        assert 0 < elapsed < .5
        assert not task.done() and not probe.admitted and not probe.initialized
        assert probe.handler.thread != threading.get_ident() and probe.handler.context == "captured-startup-context"
        assert not probe.handler.expired
        async with httpx.AsyncClient(transport=httpx.ASGITransport(probe.app), base_url="http://test") as client:
            assert (await client.get("/health")).status_code == 503
        if "cancel" in outcome:
            task.cancel("first caller interruption")
            await asyncio.sleep(0)
            task.cancel("repeated caller interruption")
            await asyncio.sleep(0)
            assert not task.done() and not probe.app.state.api_runtime_context.closed
        probe.handler.unblock.set()
        if failure is not None:
            with pytest.raises(OSError) as caught:
                await task
            assert caught.value is failure
        elif outcome == "cancel":
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await task
    finally:
        await settle_api(task, probe)
    assert_closed(probe)
    assert probe.admitted == (outcome == "success")
    assert bool(probe.initialized) == (outcome == "success")
    assert all(row["handler_finished"] for row in probe.initialized)
    record_property("startup_diagnostic", json.dumps({"warning": warning, "outcome": outcome,
        "native_thread": probe.handler.thread != threading.get_ident(), "context": probe.handler.context,
        "handler_finished": probe.handler.finished.is_set(), "owner_closed": probe.app.state.api_runtime_context.closed}))


@pytest.mark.parametrize("environment", ["production", "staging"])
@pytest.mark.parametrize("cancelled", [False, True])
async def test_forbidden_bypass_refuses_after_owned_diagnostic(tmp_path, monkeypatch, record_property, environment, cancelled):
    probe = prepare_app(tmp_path, monkeypatch, warning="bypass", environment=environment)
    task = asyncio.create_task(enter_api(probe))
    try:
        assert await asyncio.to_thread(probe.handler.entered.wait, 10)
        assert 0 < await sqlite_response(tmp_path / "responsive.db", record_property, probe.handler.started) < .5
        assert not probe.initialized and not probe.admitted and not task.done()
        if cancelled:
            task.cancel("first caller interruption")
            await asyncio.sleep(0)
            task.cancel("repeated caller interruption")
            assert not task.done()
        probe.handler.unblock.set()
        with pytest.raises(RuntimeError, match="ORKET_ALLOW_INSECURE_NO_API_KEY is forbidden") as caught:
            await task
        assert type(caught.value) is RuntimeError
        assert probe.handler.record.levelno == logging.CRITICAL
    finally:
        await settle_api(task, probe)
    assert_closed(probe)
    assert not probe.admitted and not probe.initialized


async def test_startup_captures_bound_validator_and_logger_before_root_await(tmp_path, monkeypatch):
    probe = prepare_app(tmp_path, monkeypatch, warning="tls")
    probe.handler.unblock.set()
    root_gate = SimpleNamespace(entered=threading.Event(), release=threading.Event())
    original = api_startup_service._validate_root

    def hold_root(configured_root, owned_root):
        root_gate.entered.set()
        assert root_gate.release.wait(5)
        return original(configured_root, owned_root)

    def replaced_validator(_self, _logger):
        raise AssertionError("late replacement validator was used")

    monkeypatch.setattr(api_startup_service, "_validate_root", hold_root)
    task = asyncio.create_task(enter_api(probe))
    try:
        assert await asyncio.to_thread(root_gate.entered.wait, 10)
        monkeypatch.setattr(ApiAuthenticationService, "validate_startup", replaced_validator)
        monkeypatch.setattr(api_startup_service, "LOGGER", logging.getLogger("tests.api.startup.late"))
        root_gate.release.set()
        await task
        assert probe.handler.record is not None and probe.admitted
    finally:
        root_gate.release.set()
        await settle_api(task, probe)
    assert_closed(probe)
