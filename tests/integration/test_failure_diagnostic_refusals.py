"""Layer: integration. Isolated fatal handlers and actual executor shutdown refusal."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

import pytest

import orket
from orket.adapters.execution import owned_io
from orket.application.services import application_runtime_lifetime
from orket.application.services.command_process_supervisor import CommandProcessCancelled
from orket.core.contracts.owned_command import CommandExecutionUncertain, OwnedCommandResult
from tests.helpers.failure_diagnostics import (
    DIAGNOSTIC_CONTEXT,
    assert_note,
    assert_primary_graph,
    bind_handler,
    finish_api,
    observe_hold,
    prepare_running_api,
    settle_handler,
)
from tests.helpers.runtime_cleanup_ports import NativeCleanupPort

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "tests/helpers/failure_diagnostic_worker.py"


def _selected_pythonpath():
    return os.pathsep.join((str(Path(orket.__file__).resolve().parent.parent), str(ROOT)))


def _assert_child_origins(data):
    assert Path(data["interpreter"]).resolve() == Path(sys.executable).resolve()
    assert Path(data["prefix"]).resolve() == Path(sys.prefix).resolve()
    assert Path(data["origin"]).resolve() == Path(orket.__file__).resolve()
    assert Path(data["owner_origin"]).resolve() == Path(owned_io.__file__).resolve()
    assert data["owner_sha256"] == hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest()


@pytest.mark.parametrize("route", ["warning", "preparation"])
@pytest.mark.parametrize("fatal", ["SystemExit", "KeyboardInterrupt"])
async def test_fatal_standard_handler_is_contained_before_asyncio_task_completion(tmp_path, route, fatal, record_property):
    temp = tmp_path / "temp"
    await asyncio.to_thread(temp.mkdir)
    environment = dict(os.environ, ORKET_DISABLE_SANDBOX="1", PYTHONDONTWRITEBYTECODE="1",
        TMP=str(temp), TEMP=str(temp), PYTHONPATH=await asyncio.to_thread(_selected_pythonpath))
    process = await asyncio.create_subprocess_exec(sys.executable, str(WORKER), str(tmp_path), route, fatal,
        cwd=tmp_path, env=environment, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 25)
        record_property("child_exit", process.returncode)
        assert process.returncode == 0, (stdout.decode(errors="replace"), stderr.decode(errors="replace"))
        data = json.loads(await asyncio.to_thread((tmp_path / "result.json").read_text, encoding="utf-8"))
        await asyncio.to_thread(_assert_child_origins, data)
        assert data["route"] == route and data["fatal_type"] == fatal and data["primary_identity"]
        cleanup, = [r["value"] for r in data["observations"] if r["name"] == "fixture_cleanup"]
        assert all(cleanup["sqlite_closed"]) and all(cleanup.get("engines_closed", []))
        record_property("fatal_handler_control", json.dumps(data))
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
        assert process.returncode is not None


def _closed_executor():
    # Start and join an actual native worker before installing its closed executor.
    with ThreadPoolExecutor(max_workers=1) as executor:
        worker_thread = executor.submit(threading.get_ident).result()
    return executor, worker_thread


async def test_closed_native_executor_refusal_preserves_primary_and_notes_once(tmp_path, monkeypatch, record_property):
    port = await asyncio.to_thread(NativeCleanupPort, tmp_path / "executor.sqlite3", failure=True)
    executor, worker_thread = await asyncio.to_thread(_closed_executor)
    assert worker_thread != threading.get_ident()
    logger, handler = bind_handler(monkeypatch, owned_io, "logger", "executor diagnostic", fail=False, identity=tmp_path.name)
    handler.unblock.set()
    loop, previous = asyncio.get_running_loop(), asyncio.get_running_loop()._default_executor
    try:
        try:
            await asyncio.to_thread(port.close)
        except sqlite3.OperationalError as error:
            primary = error
        else:
            raise AssertionError("real SQLite refusal did not occur")
        original_graph = primary.__cause__, primary.__context__
        loop.set_default_executor(executor)
        try:
            for _ in range(2):
                await owned_io.run_owned_diagnostic(partial(logger.error, "executor diagnostic"), primary=primary)
        finally:
            loop.set_default_executor(previous)
        assert primary is port.errors[0] and (primary.__cause__, primary.__context__) == original_graph
        assert_note(primary, failed=True)
        assert handler.calls == 0
        record_property("executor_refusal", json.dumps({"primary_identity": True, "handler_calls": 0,
                                                        "native_worker_joined": True, "attempts": 2}))
    finally:
        loop.set_default_executor(previous)
        logger.removeHandler(handler)
        handler.close()
        port.failure = False
        await asyncio.to_thread(port.close)
        closed = await asyncio.to_thread(port.observe_closed)
        record_property("fixture_cleanup", json.dumps({"sqlite_closed": [closed]}))
        assert closed


@pytest.mark.parametrize("handler_fails", [False, True])
async def test_managed_command_uncertainty_keeps_one_converted_primary(tmp_path, monkeypatch, record_property, handler_fails):
    """Actual API/SQLite cleanup; command uncertainty is a declared input, not process-cleanup proof."""
    state = await prepare_running_api(tmp_path, monkeypatch)
    lifetime = OwnedCommandResult(None, b"", b"", "supervisor_lost", False, False, "declared-control", 1, None, None, ())
    logger, handler = bind_handler(monkeypatch, application_runtime_lifetime, "LOGGER", "Application background task failed",
                                   fail=handler_fails, identity=tmp_path.name)
    closing = None

    async def invoke():
        raise CommandProcessCancelled(lifetime)

    token = DIAGNOSTIC_CONTEXT.set("managed-uncertainty-context")
    try:
        state.background = state.owner.start_background(invoke)
        assert await asyncio.to_thread(handler.entered.wait, 5)
        primary = state.owner._background_failure
        assert isinstance(primary, CommandExecutionUncertain) and primary.lifetime is lifetime
        assert handler.exceptions == [primary] and not state.owner.accepting_work
        closing = asyncio.create_task(state.owner.close())
        DIAGNOSTIC_CONTEXT.reset(token)
        token = None
        def inspect_order():
            return {"background_done": state.background.done(), "attempts": [p.attempts for p in state.ports],
                    "final_entries": len(state.final_close_entries)}
        elapsed, before, outcome = await observe_hold(closing, handler, tmp_path / "responsive.db", record_property,
                                                     before_release=inspect_order)
        assert isinstance(outcome, RuntimeError) and outcome.__cause__ is primary
        assert str(outcome) == "API runtime teardown failed for 1 owner(s)."
        assert state.owner._background_failure is primary and handler.exceptions == [primary]
        assert_note(primary, failed=handler_fails)
        assert_primary_graph(handler, primary)
        assert elapsed < .5 and before["native_thread"] and not before["watchdog_expired"]
        assert not before["task_done"] and not before["done_after_cancellation"]
        assert before["context"] == "managed-uncertainty-context"
        assert before["resource_order"] == {"background_done": False, "attempts": [0, 0], "final_entries": 0}
        states = await asyncio.gather(*(asyncio.to_thread(p.observe_closed) for p in state.ports))
        assert states == [True, True] and state.owner.engine._closed and not state.owner.closed
        record_property("managed_uncertainty", json.dumps({"one_converted_identity": True, "before": before,
                                                           "closed_before_emergency": states, "handler_fails": handler_fails}))
    finally:
        if token is not None:
            DIAGNOSTIC_CONTEXT.reset(token)
        if closing is None:
            closing = asyncio.create_task(state.owner.close())
        await settle_handler(closing, logger, handler)
        record_property("fixture_cleanup", json.dumps(await finish_api(state)))


async def test_managed_confirmed_command_cancellation_remains_cooperative(tmp_path, monkeypatch, record_property):
    """Declared confirmed cancellation stays cooperative; actual API resources still close."""
    state = await prepare_running_api(tmp_path, monkeypatch)
    lifetime = OwnedCommandResult(None, b"", b"", "cancelled", True, True, "declared-control", 1, None, None, ())
    logger, handler = bind_handler(monkeypatch, application_runtime_lifetime, "LOGGER", "Application background task failed",
                                   fail=True, identity=tmp_path.name)
    handler.unblock.set()

    async def invoke():
        raise CommandProcessCancelled(lifetime)

    try:
        await state.owner.start_background(invoke)
        assert state.owner.accepting_work and state.owner._background_failure is None and handler.calls == 0
        await state.owner.close()
        assert state.owner.closed and state.owner.engine._closed and handler.calls == 0
        assert all(await asyncio.gather(*(asyncio.to_thread(p.observe_closed) for p in state.ports)))
    finally:
        logger.removeHandler(handler)
        handler.close()
        record_property("fixture_cleanup", json.dumps(await finish_api(state)))
