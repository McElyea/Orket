"""Actual handler and SQLite barriers; emergency cleanup is excluded from proof."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextvars import ContextVar
from types import SimpleNamespace

from orket.application.services import api_runtime_preparation
from orket.application.services.application_runtime_lifetime import close_owned_resource
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.helpers.runtime_cleanup_ports import AsyncCleanupPort, NativeCleanupPort
from tests.helpers.runtime_verification_hold import sqlite_response

DIAGNOSTIC_CONTEXT = ContextVar("failure_diagnostic_context", default="unbound")
DIAGNOSTIC_NOTE = "E_OWNED_DIAGNOSTIC_FAILED"


class PrimaryFailure(RuntimeError):
    """Ordinary exception state; only the public note override is adverse."""

    def __init__(self, message):
        super().__init__(message)
        self.note_hook_calls = 0
        BaseException.add_note(self, "pre-existing primary note")

    def add_note(self, _note):
        self.note_hook_calls += 1
        raise AssertionError("Supporting diagnostics must use BaseException.add_note directly")


class HeldFailureHandler(logging.Handler):
    def __init__(self, prefix, *, fail):
        super().__init__()
        self.prefix, self.fail = prefix, fail
        self.entered, self.unblock, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.thread, self.started, self.context = None, None, None
        self.failure = OSError("secret diagnostic text must not escape into primary notes")
        self.calls, self.expired = 0, False
        self.exceptions = []
        self.exception_states = []

    def emit(self, record):
        if not record.getMessage().startswith(self.prefix):
            return
        self.calls += 1
        self.exceptions.append(record.exc_info[1] if isinstance(record.exc_info, tuple) else None)
        if (error := self.exceptions[-1]) is not None:
            self.exception_states.append((error, error.__cause__, error.__context__))
        self.thread, self.started = threading.get_ident(), time.perf_counter()
        self.context = DIAGNOSTIC_CONTEXT.get()
        self.entered.set()
        try:
            self.expired = not self.unblock.wait(2)
            if self.fail:
                raise self.failure
        finally:
            self.finished.set()


def bind_handler(monkeypatch, module, attribute, prefix, *, fail, identity):
    handler = HeldFailureHandler(prefix, fail=fail)
    logger = logging.getLogger("tests.failure.diagnostic." + identity)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    monkeypatch.setattr(module, attribute, logger)
    return logger, handler


async def observe_hold(task, handler, database, record_property, *, before_release=None):
    assert await asyncio.to_thread(handler.entered.wait, 5), "diagnostic never reached its native barrier"
    elapsed = await sqlite_response(database, record_property, handler.started)
    before = {"task_done": task.done(), "native_thread": handler.thread != threading.get_ident(),
              "watchdog_expired": handler.expired, "context": handler.context}
    for _ in range(2):
        task.cancel("repeated cancellation during diagnostic")
        await asyncio.sleep(0)
    before["done_after_cancellation"] = task.done()
    if before_release is not None:
        before["resource_order"] = before_release()
    handler.unblock.set()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
    try:
        outcome = task.result()
    except BaseException as error:  # Observe the original cancellation, not gather's synthesized instance.
        outcome = error
    return elapsed, before, outcome


async def settle_handler(task, logger, handler):
    handler.unblock.set()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
    logger.removeHandler(handler)
    handler.close()
    assert not handler.entered.is_set() or handler.finished.is_set()


def failure_tree(error):
    result, pending, visited = [], [error], set()
    while pending:
        current = pending.pop()
        if not isinstance(current, BaseException) or id(current) in visited:
            continue
        visited.add(id(current))
        result.append(current)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(current.exceptions)
        pending.append(current.__cause__)
    return result


def assert_note(primary, *, failed):
    notes = getattr(primary, "__notes__", [])
    assert notes.count(DIAGNOSTIC_NOTE) == int(failed)
    prior = ["pre-existing primary note"] if isinstance(primary, PrimaryFailure) else []
    assert [note for note in notes if note != DIAGNOSTIC_NOTE] == prior
    if isinstance(primary, PrimaryFailure):
        assert primary.note_hook_calls == 0


def assert_primary_graph(handler, primary):
    snapshots = [entry for entry in handler.exception_states if entry[0] is primary]
    assert snapshots, "diagnostic did not retain its explicit exception triple"
    assert primary.__cause__ is snapshots[0][1] and primary.__context__ is snapshots[0][2]


def prepare_failed_api(tmp_path, monkeypatch, phase, primary):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    actual_build = api_runtime_preparation.build_api_runtime_container
    owners, ports = [], []

    def acquire(*args, **kwargs):
        owner = actual_build(*args, **kwargs)
        owners.append(owner)
        for index in range(2):
            port = AsyncCleanupPort(tmp_path / f"acquired-{index}.sqlite3", failure=phase == "partial" and index == 1)
            ports.append(port)
            (kwargs["own_resource"] if phase == "partial" else owner.register_owned_resource)(port)
        if phase == "partial":
            raise primary
        return owner

    def refuse_policy(*_args, **_kwargs):
        raise primary

    monkeypatch.setattr(api_runtime_preparation, "build_api_runtime_container", acquire)
    monkeypatch.setattr(api_runtime_preparation, "capture_api_outbound_policy", refuse_policy)
    return create_api_app(CompositionConfig(project_root=tmp_path)), owners, ports


async def enter_failed_api(app):
    async with app.router.lifespan_context(app):
        raise AssertionError("failed preparation became ready")


async def prepare_running_api(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    manager = app.router.lifespan_context(app)
    await manager.__aenter__()
    owner = app.state.api_runtime_context
    ports = [await asyncio.to_thread(AsyncCleanupPort, tmp_path / f"lifespan-{i}.sqlite3") for i in range(2)]
    for port in ports:
        owner.register_owned_resource(port)
    final_close_entries, actual_close = [], owner.engine.close

    async def observe_final_close():
        final_close_entries.append(True)
        await actual_close()

    monkeypatch.setattr(owner.engine, "close", observe_final_close)
    return SimpleNamespace(app=app, manager=manager, owner=owner, ports=ports, background=None,
                           final_close_entries=final_close_entries)


async def stage_api_failure(state, kind, monkeypatch, tmp_path):
    primary = PrimaryFailure("controlled owned task failure")
    if kind == "resource":
        state.ports[1].failure = True
        return None
    if kind == "final":
        final_port = await asyncio.to_thread(AsyncCleanupPort, tmp_path / "final.sqlite3", failure=True)
        state.ports.append(final_port)
        close_engine = state.owner.engine.close

        async def close_engine_and_refuse():
            await close_engine()
            await final_port.aclose()

        monkeypatch.setattr(state.owner.engine, "close", close_engine_and_refuse)
        return None
    started = asyncio.Event()

    async def fail():
        started.set()
        if kind == "tracked":
            try:
                await asyncio.Event().wait()
            finally:
                raise primary
        raise primary

    if kind == "background":
        state.background = state.owner.start_background(fail)
    else:
        state.background = asyncio.create_task(fail())
        state.owner.track_background_task(state.background)
    await asyncio.wait_for(started.wait(), 5)
    return primary


async def finish_api(state):
    # Product close outcome/states are already recorded. Failed cached close is
    # observed again by the real lifespan exit, then emergency cleanup is explicit.
    exit_failure = None
    try:
        await state.manager.__aexit__(None, None, None)
    except (Exception, asyncio.CancelledError) as error:
        exit_failure = error  # The failed cached close must remain visible at real lifespan exit.
    finally:
        cleanup = await emergency_cleanup([state.owner], state.ports)
    assert exit_failure is state.owner._close_task.exception()
    return cleanup


async def emergency_cleanup(owners, ports):
    # Counterexample cleanup happens only after product state has been observed.
    for port in ports:
        port.failure = False
    resources = [resource for owner in owners for resource in [*reversed(owner._owned_resources), owner.engine]]
    results = []
    for resource in resources:
        try:
            await close_owned_resource(resource)
        except (Exception, asyncio.CancelledError) as error:
            results.append(error)
    for port in ports:
        await asyncio.to_thread(NativeCleanupPort.close, port)
    assert not results, results
    states = await asyncio.gather(*(asyncio.to_thread(port.observe_closed) for port in ports))
    assert all(states) and all(owner.engine._closed for owner in owners)
    assert all(owner.active_background_task_count == owner.active_request_count == 0 for owner in owners)
    return {"sqlite_closed": states, "engines_closed": [owner.engine._closed for owner in owners],
            "active_background": [owner.active_background_task_count for owner in owners],
            "active_requests": [owner.active_request_count for owner in owners]}
