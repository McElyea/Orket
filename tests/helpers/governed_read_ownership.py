"""Native holds around real read-only SQLite observations, with failure cleanup."""
from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from functools import partial
from pathlib import Path

import aiosqlite

from orket.adapters.storage.async_governed_agent_wake_repository import AsyncGovernedAgentWakeRepository
from orket.application.services.governed_agent_commands import GovernedAgentCommands
from orket.application.services.governed_agent_supervisor import GovernedAgentWakeClaimGuard
from tests.helpers.runtime_verification_hold import sqlite_response, wait_entered
from tests.integration.test_async_governed_agent_wake_repository import _request
from tests.integration.test_governed_agent_replay_evidence import _prepare
from tests.integration.test_sqlite_wal_admission import _assert_closed

NOW = "2026-09-07T12:00:02Z"


async def prepare_reads(path):
    await _prepare(path, 1)
    repository = AsyncGovernedAgentWakeRepository(path)
    await repository.enqueue(_request())
    claim = await repository.claim_next(owner_id="read-owner", now_utc=NOW,
        lease_expires_at_utc="2026-09-07T12:01:02Z", max_active_claims=1)
    assert claim.authority is not None
    return claim.authority


async def invoke_read(family, path, authority):
    if family == "replay":
        return await GovernedAgentCommands(path).inspect(run_id="run-1", replay=True)
    guard = GovernedAgentWakeClaimGuard(repository=AsyncGovernedAgentWakeRepository(path),
        authority=authority, now_utc=lambda: NOW)
    await guard.ensure_active()
    return "active"


class NativeReadProbe:
    """Only target read-only connections are instrumented; SQL/results stay real."""

    def __init__(self, monkeypatch, path, boundary, *, failure=None):
        self.path, self.boundary, self.failure = path, boundary, failure
        self.entered, self.release, self.finished = (threading.Event() for _ in range(3))
        self.thread, self.expired = None, False
        self.native, self.connections, self.path_calls = [], [], []
        self._observe_paths(monkeypatch)
        self._observe_connections(monkeypatch)

    def _pause(self, operation):
        if self.entered.is_set():
            return operation()
        self.thread = threading.get_ident()
        self.entered.set()
        try:
            self.expired = not self.release.wait(10)
            assert not self.expired, "native read hold was not released"
            result = operation()
            if self.failure is not None:
                raise self.failure
            return result
        finally:
            self.finished.set()

    def _observe_paths(self, monkeypatch):
        def observe(name, original):
            def observed(path, *args, **kwargs):
                call = partial(original, path, *args, **kwargs)
                if path.name == self.path.name:
                    self.path_calls.append((name, path))
                    return self._pause(call) if self.boundary == name else call()
                return call()

            return observed

        for name in ("resolve", "exists"):
            monkeypatch.setattr(Path, name, observe(name, getattr(Path, name)))

    def _observe_connections(self, monkeypatch):
        original_native, original_async = sqlite3.connect, aiosqlite.connect
        probe = self

        class ObservedConnection(sqlite3.Connection):
            closed = False

            def execute(self, sql, *args, **kwargs):
                call = partial(super().execute, sql, *args, **kwargs)
                return probe._pause(call) if probe.boundary == "query" else call()

            def close(self):
                call = super().close
                if probe.boundary == "close":
                    probe._pause(call)
                else:
                    call()
                self.closed = True

        def native(database, *args, **kwargs):
            if not self._selected(database):
                return original_native(database, *args, **kwargs)
            # Permit fixture-only recovery after an opening abandons its worker.
            # Normal use/close still runs on aiosqlite's real native worker, and
            # product closure is asserted before this recovery may run.
            kwargs.update(factory=ObservedConnection, check_same_thread=False)
            connection = original_native(database, *args, **kwargs)
            self.native.append(connection)
            if self.boundary == "connect":
                try:
                    return self._pause(lambda: connection)
                except BaseException:
                    connection.close()
                    raise
            return connection

        def asynchronous(database, *args, **kwargs):
            connection = original_async(database, *args, **kwargs)
            if self._selected(database):
                self.connections.append(connection)
            return connection

        monkeypatch.setattr(sqlite3, "connect", native)
        monkeypatch.setattr(aiosqlite, "connect", asynchronous)

    def _selected(self, database):
        return str(database) == self.path.as_uri() + "?mode=ro"

    async def assert_settled(self, *, held=True):
        assert (self.finished.is_set() if held else not self.entered.is_set()) and not self.expired
        assert all(connection.closed for connection in self.native), "product left a native connection open"
        await _assert_closed(self.connections)

    async def cleanup(self, *tasks):
        self.release.set()
        try:
            await asyncio.gather(*(task for task in tasks if task is not None), return_exceptions=True)
        finally:
            try:
                if self.entered.is_set():
                    assert await asyncio.to_thread(self.finished.wait, 3)
                await asyncio.gather(*(connection.close() for connection in self.connections), return_exceptions=True)
            finally:
                # Never turn failed pre-cleanup closure assertions into a pass.
                pending = [connection for connection in self.native if not connection.closed]
                outcomes = await asyncio.gather(*(asyncio.to_thread(connection.close) for connection in pending),
                                                return_exceptions=True)
                for outcome in outcomes:
                    if isinstance(outcome, BaseException):
                        raise outcome
                await _assert_closed(self.connections)


async def interrupt_held_read(task, probe, mode, database, record_property):
    await wait_entered(probe)
    assert probe.thread != threading.get_ident() and not probe.finished.is_set()
    waiter = task
    try:
        if mode == "timeout":
            waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
            started = time.perf_counter()
            while task.cancelling() == 0 and not task.done() and time.perf_counter() - started < 2:
                await asyncio.wait({waiter}, timeout=0.005)
            record_property("observed_deadline_cancellation_requests", task.cancelling())
            assert task.cancelling() == 1, "wait_for did not cancel the actual held caller"
        else:
            task.cancel("first read interruption")
            await asyncio.sleep(0)
            task.cancel("repeated read interruption")
        assert await sqlite_response(database, record_property) < 0.5
        assert not task.done() and not waiter.done(), "read returned before its native attempt settled"
        assert not probe.finished.is_set() and not probe.expired
    except BaseException:
        # The test caller cannot receive this waiter on a failing opening.
        probe.release.set()
        await asyncio.gather(waiter, return_exceptions=True)
        raise
    return waiter
