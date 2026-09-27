"""Real SQLite/filesystem fixtures with explicit repository scheduling barriers."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleEventRecord


def event(identity: str) -> SandboxLifecycleEventRecord:
    return SandboxLifecycleEventRecord(event_id=identity, sandbox_id="sandbox-proof", event_kind="lifecycle",
        event_type="sandbox.cleanup_scheduled", created_at="2026-09-27T00:00:00+00:00",
        payload={"nested": {"value": "original"}})


async def failed_repository(root: Path) -> AsyncSandboxLifecycleRepository:
    database = root / "not-a-database-directory"
    await asyncio.to_thread(database.mkdir, parents=True, exist_ok=True)
    return AsyncSandboxLifecycleRepository(database)


class GateRepository:
    def __init__(self, repository):
        self.repository = repository
        self.entered, self.release = asyncio.Event(), asyncio.Event()

    async def append_event(self, record):
        self.entered.set()
        await asyncio.wait_for(self.release.wait(), 10)
        await self.repository.append_event(record)


async def spool_records(path: Path):
    content = await asyncio.to_thread(path.read_text, encoding="utf-8")
    return [json.loads(line) for line in content.splitlines() if line.strip()]


def hold_native(monkeypatch, target, name, *, failure=False):
    original = getattr(target, name)
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(),
                            finished=threading.Event(), thread=None)

    def held(*args, **kwargs):
        if state.entered.is_set():
            return original(*args, **kwargs)
        state.thread = threading.get_ident()
        state.entered.set()
        try:
            assert state.release.wait(10), "fixture did not release its native operation"
            result = original(*args, **kwargs)
            if failure:
                raise OSError("controlled native completion failure")
            return result
        finally:
            state.finished.set()

    monkeypatch.setattr(target, name, held)
    return state


class HeldDiagnosticHandler(logging.Handler):
    def __init__(self, *, failure: bool):
        super().__init__()
        self.failure = failure
        self.hold = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                                    thread=None, started=None)
        self.records = []

    def emit(self, record):
        self.hold.thread, self.hold.started = threading.get_ident(), time.perf_counter()
        self.hold.entered.set()
        try:
            if not self.hold.release.wait(3):
                raise OSError("diagnostic fixture watchdog expired")
            self.records.append(record)
            if self.failure:
                raise OSError("controlled diagnostic failure")
        finally:
            self.hold.finished.set()
