"""Layer: integration. Required replay diagnostics use real handlers and SQLite effects."""
from __future__ import annotations

import asyncio
import logging
import threading

import pytest

from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services.sandbox_lifecycle_event_service import SandboxLifecycleEventService
from tests.helpers.runtime_verification_hold import settle, sqlite_response
from tests.helpers.sandbox_event_ownership import HeldDiagnosticHandler, event, failed_repository, spool_records

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("failure", [False, True])
# Layer: integration
async def test_replay_diagnostic_settles_before_cancellation(tmp_path, record_property, failure):
    spool = tmp_path / "events.jsonl"
    failed = await failed_repository(tmp_path)
    producer = SandboxLifecycleEventService(repository=failed, spool_path=spool)
    for identity in ("first", "second"):
        assert await producer.emit(event(identity)) == "fallback"
    original = await asyncio.to_thread(spool.read_bytes)
    repository = AsyncSandboxLifecycleRepository(tmp_path / "events.db")

    class PartiallyAvailableRepository:
        async def append_event(self, record):
            selected = repository if record.event_id == "first" else failed
            await selected.append_event(record)

    service = SandboxLifecycleEventService(repository=PartiallyAvailableRepository(), spool_path=spool)
    logger = logging.getLogger(f"tests.sandbox.diagnostic.{tmp_path.name}")
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    handler = HeldDiagnosticHandler(failure=failure)
    hold = handler.hold
    logger.addHandler(handler)
    service._logger = logger
    task = asyncio.create_task(service.replay_spool())
    try:
        assert await asyncio.to_thread(hold.entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        assert await sqlite_response(tmp_path / "responsive.db", record_property, hold.started) < 0.5
        assert hold.thread != threading.get_ident() and not task.done()
        hold.release.set()
        with pytest.raises(OSError if failure else asyncio.CancelledError):
            await task
        assert [row.event_id for row in await repository.list_events()] == ["first"]
        diagnostic, = handler.records
        assert diagnostic.sandbox_lifecycle_event_id == "second" and diagnostic.retry_count == 1
        assert diagnostic.max_replay_attempts == 3 and diagnostic.spool_path == str(spool)
        assert diagnostic.exc_info[1] is not None
        if failure:
            assert await asyncio.to_thread(spool.read_bytes) == original
        else:
            row, = await spool_records(spool)
            assert row["record"]["event_id"] == "second" and row["retry_count"] == 1
    finally:
        await settle(task, hold)
        logger.removeHandler(handler)
        handler.close()
    await producer._append_spool(event("successor"))
