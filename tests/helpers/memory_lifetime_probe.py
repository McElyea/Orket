"""Held real native memory operations; no replacement SQLite result or deadline."""
from __future__ import annotations

import asyncio
import threading
from time import perf_counter

from orket.adapters.storage import sqlite_connection
from tests.helpers.memory_state_probe import rows
from tests.integration.test_sqlite_wal_admission import _assert_closed, _observe_connections


class NativeMemoryHold:
    def __init__(self, monkeypatch):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.expired = False
        self.thread_id = None
        self.connections, _ = _observe_connections(monkeypatch)

    def hold(self):
        self.thread_id = threading.get_ident()
        self.entered.set()
        self.expired = not self.release.wait(10)

    def sqlite(self, monkeypatch, prefix):
        original = sqlite_connection.ensure_wal_mode

        async def observe(connection):
            result = await original(connection)

            def trace(statement):
                if " ".join(statement.upper().split()).startswith(prefix) and not self.entered.is_set():
                    self.hold()

            await connection.set_trace_callback(trace)
            return result

        monkeypatch.setattr(sqlite_connection, "ensure_wal_mode", observe)

    async def interrupt(self, operation, mode, independent_path):
        timeout = asyncio.timeout(None)

        async def invoke():
            async with timeout:
                return await operation

        task = asyncio.create_task(invoke())
        try:
            assert await asyncio.wait_for(asyncio.to_thread(self.entered.wait, 10), 11)
            assert self.thread_id != threading.get_ident()
            started = perf_counter()
            assert await rows(independent_path, "SELECT 41 + 1") == [(42,)]
            elapsed = perf_counter() - started
            assert elapsed < 0.5
            if mode == "timeout":
                timeout.reschedule(asyncio.get_running_loop().time() + 0.05)
            else:
                task.cancel()
            await asyncio.sleep(0.1)
            if mode == "repeated":
                task.cancel()
            await asyncio.sleep(0.7)
            assert not task.done(), "memory operation escaped before its native work drained"
        finally:
            self.release.set()
            outcome, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
            await _assert_closed(self.connections)
        assert not self.expired
        assert isinstance(outcome, TimeoutError if mode == "timeout" else asyncio.CancelledError), outcome
        print(f"[memory-lifetime] path=primary result=success interruption={mode} independent_sqlite_seconds={elapsed:.9f}")
        return elapsed
