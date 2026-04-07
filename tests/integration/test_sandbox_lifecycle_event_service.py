# Layer: integration

from __future__ import annotations

import asyncio
import logging
import os

import aiofiles
import pytest

from orket.application.services.sandbox_lifecycle_event_service import SandboxLifecycleEventService, SpoolReplayResult
from orket.core.domain.sandbox_lifecycle import SandboxLifecycleError
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleEventRecord


class _Repo:
    def __init__(self, fail: bool = False, delay: float = 0.0):
        self.fail = fail
        self.delay = delay
        self.events: list[SandboxLifecycleEventRecord] = []

    async def append_event(self, record: SandboxLifecycleEventRecord) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("primary-down")
        self.events.append(record)


def _event(event_id: str) -> SandboxLifecycleEventRecord:
    return SandboxLifecycleEventRecord(
        event_id=event_id,
        sandbox_id="sb-1",
        event_kind="lifecycle",
        event_type="sandbox.cleanup_scheduled",
        created_at="2026-03-11T00:00:00+00:00",
        payload={"reason_code": "lease_expired"},
    )


@pytest.mark.asyncio
async def test_emit_uses_primary_store_when_available(tmp_path) -> None:
    repo = _Repo()
    service = SandboxLifecycleEventService(repository=repo, spool_path=tmp_path / "events.jsonl")

    path = await service.emit(_event("evt-1"))

    assert path == "primary"
    assert [event.event_id for event in repo.events] == ["evt-1"]
    assert not (tmp_path / "events.jsonl").exists()


@pytest.mark.asyncio
async def test_emit_falls_back_to_local_spool_when_primary_store_fails(tmp_path) -> None:
    repo = _Repo(fail=True)
    spool_path = tmp_path / "events.jsonl"
    service = SandboxLifecycleEventService(repository=repo, spool_path=spool_path)

    path = await service.emit(_event("evt-1"))

    assert path == "fallback"
    assert spool_path.exists()
    async with aiofiles.open(spool_path, encoding="utf-8") as handle:
        content = await handle.read()
    assert "evt-1" in content


@pytest.mark.asyncio
async def test_replay_spool_rehydrates_primary_store_and_clears_spool(tmp_path) -> None:
    repo = _Repo(fail=True)
    spool_path = tmp_path / "events.jsonl"
    service = SandboxLifecycleEventService(repository=repo, spool_path=spool_path)
    await service.emit(_event("evt-1"))
    repo.fail = False

    replayed = await service.replay_spool()

    assert replayed == SpoolReplayResult(replayed=1, requeued=0, dead_lettered=0)
    assert [event.event_id for event in repo.events] == ["evt-1"]
    assert not spool_path.exists()


@pytest.mark.asyncio
async def test_emit_raises_when_primary_and_spool_sinks_fail(tmp_path) -> None:
    repo = _Repo(fail=True)
    service = SandboxLifecycleEventService(
        repository=repo,
        spool_path=tmp_path,
    )

    with pytest.raises(SandboxLifecycleError, match="event sinks failed"):
        await service.emit(_event("evt-1"))


@pytest.mark.asyncio
async def test_replay_spool_requeues_then_dead_letters_after_retry_limit(tmp_path, caplog) -> None:
    repo = _Repo(fail=True)
    spool_path = tmp_path / "events.jsonl"
    service = SandboxLifecycleEventService(repository=repo, spool_path=spool_path)
    await service.emit(_event("evt-1"))
    caplog.set_level(logging.WARNING)

    first = await service.replay_spool()
    second = await service.replay_spool()
    third = await service.replay_spool()

    assert first == SpoolReplayResult(replayed=0, requeued=1, dead_lettered=0)
    assert second == SpoolReplayResult(replayed=0, requeued=1, dead_lettered=0)
    assert third == SpoolReplayResult(replayed=0, requeued=0, dead_lettered=1)
    assert not spool_path.exists()
    assert service.dead_letter_path.exists()
    async with aiofiles.open(service.dead_letter_path, encoding="utf-8") as handle:
        dead_letter_content = await handle.read()
    assert "evt-1" in dead_letter_content
    assert '"retry_count":3' in dead_letter_content
    assert any(
        getattr(record, "sandbox_lifecycle_event_id", "") == "evt-1"
        and getattr(record, "retry_count", 0) >= 1
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_replay_spool_atomic_rewrite_keeps_original_when_commit_fails(tmp_path, monkeypatch) -> None:
    repo = _Repo(fail=True)
    spool_path = tmp_path / "events.jsonl"
    service = SandboxLifecycleEventService(repository=repo, spool_path=spool_path)
    await service.emit(_event("evt-1"))
    async with aiofiles.open(spool_path, encoding="utf-8") as handle:
        original_content = await handle.read()

    def fail_replace(src, dst):  # noqa: ANN001
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        await service.replay_spool()

    async with aiofiles.open(spool_path, encoding="utf-8") as handle:
        retained_content = await handle.read()
    assert retained_content == original_content
    assert spool_path.with_suffix(spool_path.suffix + ".tmp").exists()


@pytest.mark.asyncio
async def test_concurrent_replay_spool_calls_do_not_double_replay_or_lose_records(tmp_path) -> None:
    repo = _Repo(delay=0.05)
    spool_path = tmp_path / "events.jsonl"
    service = SandboxLifecycleEventService(repository=repo, spool_path=spool_path)
    await service._append_spool(_event("evt-1"))

    first, second = await asyncio.gather(service.replay_spool(), service.replay_spool())

    assert sorted([first.replayed, second.replayed]) == [0, 1]
    assert [event.event_id for event in repo.events] == ["evt-1"]
    assert not spool_path.exists()
    assert not service.lock_path.exists()
