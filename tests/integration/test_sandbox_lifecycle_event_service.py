# Layer: integration

from __future__ import annotations

import aiofiles
import pytest

from orket.application.services.sandbox_lifecycle_event_service import SandboxLifecycleEventService
from orket.core.domain.sandbox_lifecycle import SandboxLifecycleError
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleEventRecord


class _Repo:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.events: list[SandboxLifecycleEventRecord] = []

    async def append_event(self, record: SandboxLifecycleEventRecord) -> None:
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
    async with aiofiles.open(spool_path, "r", encoding="utf-8") as handle:
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

    assert replayed == 1
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
