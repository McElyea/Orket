"""Layer: integration. Actual spool files, native handles and SQLite publication."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services.sandbox_lifecycle_event_publisher import SandboxLifecycleEventPublisher
from orket.application.services.sandbox_lifecycle_event_service import SandboxLifecycleEventService
from orket.core.domain.sandbox_lifecycle import SandboxLifecycleError
from tests.helpers.runtime_verification_hold import cancel_while_held, settle, sqlite_response
from tests.helpers.sandbox_event_ownership import GateRepository, event, failed_repository, spool_records

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
async def test_cancelled_lock_adoption_settles_descriptor(tmp_path, monkeypatch, record_property):
    repository = AsyncSandboxLifecycleRepository(tmp_path / "events.db")
    service = SandboxLifecycleEventService(repository=repository, spool_path=tmp_path / "events.jsonl")
    await service._append_spool(event("held"))
    hold = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event())
    descriptors, native_open = [], os.open

    def held_open(path, flags, *args, **kwargs):
        descriptor = native_open(path, flags, *args, **kwargs)
        if str(path).endswith(".lock") and not hold.entered.is_set():
            descriptors.append(descriptor)
            hold.entered.set()
            try:
                assert hold.release.wait(10)
            finally:
                hold.finished.set()
        return descriptor

    monkeypatch.setattr(os, "open", held_open)
    task = asyncio.create_task(service.replay_spool())
    try:
        await cancel_while_held(task, hold, tmp_path / "responsive.db", record_property)
        with pytest.raises(OSError):
            os.fstat(descriptors[0])
        assert [row.event_id for row in await repository.list_events()] == ["held"]
        assert (await service.replay_spool()).lock_acquired
    finally:
        await settle(task, hold)
        # The opening implementation leaks; this fixture closes only its observed fd.
        for descriptor in descriptors:
            try:
                os.fstat(descriptor)
            except OSError:
                continue
            os.close(descriptor)


# Layer: integration
async def test_fallback_payload_keeps_publisher_identity(tmp_path):
    gate = GateRepository(await failed_repository(tmp_path))
    publisher = SandboxLifecycleEventPublisher(repository=gate, spool_path=tmp_path / "events.jsonl")
    payload = {"nested": {"value": "original"}}
    task = asyncio.create_task(publisher.emit(sandbox_id="sandbox-proof", created_at="2026-09-27T00:00:00+00:00",
        event_type="sandbox.cleanup_scheduled", payload=payload))
    try:
        await asyncio.wait_for(gate.entered.wait(), 5)
        payload["nested"]["value"] = "mutated"
        gate.release.set()
        assert await task == "fallback"
    finally:
        gate.release.set()
        await asyncio.gather(task, return_exceptions=True)
    record = (await spool_records(tmp_path / "events.jsonl"))[0]["record"]
    assert record["payload"] == {"nested": {"value": "original"}}
    blob = json.dumps(record["payload"], sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"sandbox-proof:sandbox.cleanup_scheduled:2026-09-27T00:00:00+00:00:{blob}".encode()).hexdigest()
    assert record["event_id"] == f"sandbox.cleanup_scheduled:{digest}"


# Layer: integration
async def test_fallback_busy_refuses_and_retry_survives_replay(tmp_path):
    spool = tmp_path / "events.jsonl"
    producer = SandboxLifecycleEventService(repository=await failed_repository(tmp_path), spool_path=spool)
    assert await producer.emit(event("first")) == "fallback"
    repository = AsyncSandboxLifecycleRepository(tmp_path / "events.db")
    gate = GateRepository(repository)
    replay = SandboxLifecycleEventService(repository=gate, spool_path=spool)
    task = asyncio.create_task(replay.replay_spool())
    try:
        await asyncio.wait_for(gate.entered.wait(), 5)
        with pytest.raises(SandboxLifecycleError, match="owner_busy"):
            await producer.emit(event("second"))
        assert [row["record"]["event_id"] for row in await spool_records(spool)] == ["first"]
    finally:
        gate.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert (await task).replayed == 1
    assert await producer.emit(event("second")) == "fallback"
    assert (await replay.replay_spool()).replayed == 1
    assert [row.event_id for row in await repository.list_events()] == ["first", "second"]


# Layer: integration
async def test_emit_captures_root_record_and_repository(tmp_path, monkeypatch):
    before, after = tmp_path / "before", tmp_path / "after"
    await asyncio.to_thread(before.mkdir)
    await asyncio.to_thread(after.mkdir)
    gate = GateRepository(await failed_repository(before))
    monkeypatch.chdir(before)
    service = SandboxLifecycleEventService(repository=gate, spool_path="events.jsonl")
    selected = event("captured")
    task = asyncio.create_task(service.emit(selected))
    try:
        await asyncio.wait_for(gate.entered.wait(), 5)
        monkeypatch.chdir(after)
        selected.payload["nested"]["value"] = "mutated"
        service.spool_path = after / "changed.jsonl"
        service.dead_letter_path = after / "changed.deadletter"
        service.lock_path = after / "changed.lock"
        service.repository = AsyncSandboxLifecycleRepository(after / "changed.db")
        gate.release.set()
        assert await task == "fallback"
    finally:
        gate.release.set()
        await asyncio.gather(task, return_exceptions=True)
    record = (await spool_records(before / "events.jsonl"))[0]["record"]
    assert record["payload"]["nested"]["value"] == "original"
    assert list(after.iterdir()) == []


# Layer: integration
async def test_replay_captures_paths_repository_and_retry_policy(tmp_path):
    spool = tmp_path / "events.jsonl"
    failed = await failed_repository(tmp_path)
    producer = SandboxLifecycleEventService(repository=failed, spool_path=spool)
    for identity in ("first", "second"):
        assert await producer.emit(event(identity)) == "fallback"
    gate = GateRepository(failed)
    replay = SandboxLifecycleEventService(repository=gate, spool_path=spool)
    task = asyncio.create_task(replay.replay_spool())
    try:
        await asyncio.wait_for(gate.entered.wait(), 5)
        replay.spool_path = tmp_path / "changed.jsonl"
        replay.dead_letter_path = tmp_path / "changed.deadletter"
        replay.lock_path = tmp_path / "changed.lock"
        replay.max_replay_attempts = 1
        replay.repository = AsyncSandboxLifecycleRepository(tmp_path / "changed.db")
        gate.release.set()
        result = await task
    finally:
        gate.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert (result.replayed, result.requeued, result.dead_lettered) == (0, 2, 0)
    rows = await spool_records(spool)
    assert [(row["record"]["event_id"], row["retry_count"]) for row in rows] == [("first", 1), ("second", 1)]
    assert not list(tmp_path.glob("changed*"))


# Layer: integration
async def test_reentrant_fallback_refuses_without_deadlock(tmp_path):
    spool = tmp_path / "events.jsonl"
    failed = await failed_repository(tmp_path)
    producer = SandboxLifecycleEventService(repository=failed, spool_path=spool)
    assert await producer.emit(event("first")) == "fallback"
    repository = AsyncSandboxLifecycleRepository(tmp_path / "events.db")
    refusals = []

    class ReentrantRepository:
        async def append_event(self, record):
            try:
                await producer.emit(event("nested"))
            except SandboxLifecycleError as exc:
                refusals.append(str(exc))
            await repository.append_event(record)

    replay = SandboxLifecycleEventService(repository=ReentrantRepository(), spool_path=spool)
    assert (await asyncio.wait_for(replay.replay_spool(), 5)).replayed == 1
    assert len(refusals) == 1 and "owner_busy" in refusals[0]
    assert [row.event_id for row in await repository.list_events()] == ["first"]
    assert not await asyncio.to_thread(spool.exists)


# Layer: integration
async def test_failed_primary_cannot_replace_captured_fallback_payload(tmp_path):
    failed = await failed_repository(tmp_path)

    class MutatingRepository:
        async def append_event(self, record):
            record.payload["nested"]["value"] = "repository mutation"
            await failed.append_event(record)

    service = SandboxLifecycleEventService(repository=MutatingRepository(), spool_path=tmp_path / "events.jsonl")
    selected = event("retained")
    assert await service.emit(selected) == "fallback"
    assert selected.payload["nested"]["value"] == "original"
    assert (await spool_records(service.spool_path))[0]["record"]["payload"]["nested"]["value"] == "original"


@pytest.mark.parametrize("cancelled", [False, True])
# Layer: integration
async def test_primary_sqlite_publication_retains_captured_event(tmp_path, record_property, cancelled):
    repository = AsyncSandboxLifecycleRepository(tmp_path / "events.db")
    gate = GateRepository(repository)
    service = SandboxLifecycleEventService(repository=gate, spool_path=tmp_path / "events.jsonl")
    selected = event("retained")
    task = asyncio.create_task(service.emit(selected))
    try:
        await asyncio.wait_for(gate.entered.wait(), 5)
        selected.payload["nested"]["value"] = "mutated"
        if cancelled:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            assert await sqlite_response(tmp_path / "responsive.db", record_property) < 0.5
            assert not task.done()
        gate.release.set()
        if cancelled:
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            assert await task == "primary"
    finally:
        gate.release.set()
        await asyncio.gather(task, return_exceptions=True)
    record, = await repository.list_events()
    assert record.payload["nested"]["value"] == "original"
    assert not await asyncio.to_thread(service.spool_path.exists)


@pytest.mark.parametrize("retry_limit", [1, 3])
# Layer: integration
async def test_failed_replay_preserves_owned_event_for_retry(tmp_path, retry_limit):
    failed = await failed_repository(tmp_path)
    spool = tmp_path / "events.jsonl"
    selected = event("retained")
    producer = SandboxLifecycleEventService(repository=failed, spool_path=spool)
    assert await producer.emit(selected) == "fallback"

    class MutatingReplayRepository:
        async def append_event(self, record):
            record.event_id = "repository replacement"
            record.payload["nested"]["value"] = "repository mutation"
            await failed.append_event(record)

    replay = SandboxLifecycleEventService(repository=MutatingReplayRepository(), spool_path=spool,
                                           max_replay_attempts=retry_limit)
    result = await replay.replay_spool()
    assert (result.replayed, result.requeued, result.dead_lettered) == ((0, 0, 1) if retry_limit == 1 else (0, 1, 0))
    row, = await spool_records(replay.dead_letter_path if retry_limit == 1 else spool)
    assert row == {"record": selected.model_dump(mode="json"), "retry_count": 1}
