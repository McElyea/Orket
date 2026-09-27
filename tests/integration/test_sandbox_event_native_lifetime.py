"""Layer: integration. Native spool work and caller interruption settle together."""
from __future__ import annotations

import asyncio
import os
import threading

import pytest

from orket.adapters.storage import local_file_lock as native
from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services.sandbox_lifecycle_event_service import SandboxLifecycleEventService
from orket.core.domain.sandbox_lifecycle import SandboxLifecycleError
from tests.helpers.runtime_verification_hold import (
    cancel_while_held,
    hold_path,
    hold_stream,
    settle,
    sqlite_response,
    timeout_while_held,
    wait_entered,
)
from tests.helpers.sandbox_event_ownership import event, failed_repository, hold_native, spool_records

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("stage", ["emit-open", "emit-write", "emit-close", "replay-read", "replay-replace",
                                  "replay-unlink", "release"])
@pytest.mark.parametrize("interruption", ["cancel", "timeout"])
# Layer: integration
async def test_native_work_retains_owner_until_settled(tmp_path, monkeypatch, record_property, stage, interruption):
    spool = tmp_path / "events.jsonl"
    failed = await failed_repository(tmp_path)
    repository = AsyncSandboxLifecycleRepository(tmp_path / "events.db")
    service = SandboxLifecycleEventService(repository=failed if stage.startswith("emit") or stage == "replay-replace"
                                           else repository, spool_path=spool)
    if not stage.startswith("emit"):
        await service._append_spool(event("retained"))
    if stage.startswith("emit"):
        hold = hold_stream(monkeypatch, spool, stage.split("-")[1])
    elif stage == "replay-read":
        hold = hold_stream(monkeypatch, spool, "readlines")
    elif stage == "replay-replace":
        hold = hold_native(monkeypatch, os, "replace")
    elif stage == "replay-unlink":
        hold = hold_path(monkeypatch, "unlink", spool)
    else:
        hold = hold_native(monkeypatch, native, "_release")
    task = asyncio.create_task(service.emit(event("retained")) if stage.startswith("emit") else service.replay_spool())
    try:
        if interruption == "cancel":
            await cancel_while_held(task, hold, tmp_path / "responsive.db", record_property)
        else:
            await timeout_while_held(task, hold, tmp_path / "responsive.db", record_property)
        assert hold.thread != threading.get_ident()
        assert all(stream.closed for stream in getattr(hold, "streams", []))
    finally:
        await settle(task, hold)
    if stage.startswith("emit") or stage == "replay-replace":
        assert (await spool_records(spool))[0]["record"]["event_id"] == "retained"
    else:
        assert [row.event_id for row in await repository.list_events()] == ["retained"]
    # A fresh operation uses the retained lock identity after the interrupted owner released it.
    await service._append_spool(event("successor"))


@pytest.mark.parametrize("stage", ["fallback-write", "release"])
# Layer: integration
async def test_native_failure_during_cancellation_remains_failure(tmp_path, monkeypatch, record_property, stage):
    spool = tmp_path / "events.jsonl"
    repository = AsyncSandboxLifecycleRepository(tmp_path / "events.db")
    service = SandboxLifecycleEventService(repository=await failed_repository(tmp_path)
                                           if stage == "fallback-write" else repository, spool_path=spool)
    if stage == "release":
        await service._append_spool(event("partial"))
        hold = hold_native(monkeypatch, native, "_release", failure=True)
        operation = service.replay_spool()
    else:
        hold = hold_stream(monkeypatch, spool, "write", failure=True)
        operation = service.emit(event("partial"))
    task = asyncio.create_task(operation)
    try:
        await wait_entered(hold)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        assert await sqlite_response(tmp_path / "responsive.db", record_property) < 0.5
        assert not task.done()
        hold.release.set()
        if stage == "fallback-write":
            with pytest.raises(SandboxLifecycleError, match="primary=.*spool=controlled native stream failure") as caught:
                await task
            assert isinstance(caught.value.__cause__, OSError)
            assert (await spool_records(spool))[0]["record"]["event_id"] == "partial"
            assert all(stream.closed for stream in hold.streams)
        else:
            with pytest.raises(OSError, match="controlled native completion failure"):
                await task
            assert [row.event_id for row in await repository.list_events()] == ["partial"]
    finally:
        await settle(task, hold)
    await service._append_spool(event("successor"))
