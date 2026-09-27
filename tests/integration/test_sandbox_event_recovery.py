"""Layer: integration. Actual process ownership, SQLite recovery and retained partial effects."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

import orket
from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services import sandbox_lifecycle_event_service
from orket.application.services.sandbox_lifecycle_event_service import SandboxLifecycleEventService
from orket.core.domain.sandbox_lifecycle import SandboxLifecycleError
from tests.helpers.sandbox_event_ownership import event, failed_repository, spool_records

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROOT = Path(__file__).resolve().parents[2]


def bound_paths(values):
    return {name: str(Path(value).resolve()) for name, value in values.items()}


@pytest.mark.parametrize("ending", ["release", "killed"])
# Layer: integration
async def test_process_exit_releases_native_identity_for_replay(tmp_path, ending, record_property):
    spool, database = tmp_path / "events.jsonl", tmp_path / "events.db"
    producer = SandboxLifecycleEventService(repository=await failed_repository(tmp_path), spool_path=spool)
    assert await producer.emit(event("retained")) == "fallback"
    repository = AsyncSandboxLifecycleRepository(database)
    replay = SandboxLifecycleEventService(repository=repository, spool_path=spool)
    expected = await asyncio.to_thread(bound_paths, {"origin": orket.__file__,
        "service_origin": sandbox_lifecycle_event_service.__file__, "executable": sys.executable, "prefix": sys.prefix})
    child = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / "tests/helpers/sandbox_event_lock_worker.py"),
        str(spool), str(database), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env={**os.environ, "PYTHONPATH": os.pathsep.join(
            (str(Path(expected["origin"]).parent.parent), str(ROOT))), "ORKET_DISABLE_SANDBOX": "1"})
    try:
        barrier = json.loads(await asyncio.wait_for(child.stdout.readline(), 15))
        assert barrier["barrier"] == "replay_owner_held"
        observed = await asyncio.to_thread(bound_paths, {name: barrier[name] for name in expected})
        record_property("child_binding", json.dumps(observed, sort_keys=True))
        record_property("test_harness", str(ROOT))
        assert observed == expected
        lock, = list(spool.with_name(spool.name + ".owners").glob("*.lock"))
        before = await asyncio.to_thread(lock.stat)
        assert not (await replay.replay_spool()).lock_acquired
        with pytest.raises(SandboxLifecycleError, match="owner_busy"):
            await producer.emit(event("refused"))
        if ending == "killed":
            child.kill()
            await asyncio.wait_for(child.communicate(), 15)
            assert (await replay.replay_spool()).replayed == 1
        else:
            _, errors = await asyncio.wait_for(child.communicate(b"release\n"), 15)
            assert child.returncode == 0, errors.decode(errors="replace")
            assert (await replay.replay_spool()).replayed == 0
        after = await asyncio.to_thread(lock.stat)
        assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
        assert [row.event_id for row in await repository.list_events()] == ["retained"]
        assert not await asyncio.to_thread(spool.exists)
    finally:
        if child.returncode is None:
            child.kill()
        await child.communicate()


@pytest.mark.parametrize("spool_present", [True, False])
@pytest.mark.parametrize("operation", ["emit", "replay"])
# Layer: integration
async def test_legacy_sentinel_refuses_without_deleting_evidence(tmp_path, spool_present, operation):
    service = SandboxLifecycleEventService(repository=await failed_repository(tmp_path), spool_path=tmp_path / "events.jsonl")
    if spool_present:
        assert await service.emit(event("retained")) == "fallback"
    original = await asyncio.to_thread(service.spool_path.read_bytes) if spool_present else None
    sentinel = b"uncertain legacy owner evidence"
    await asyncio.to_thread(service.lock_path.write_bytes, sentinel)
    with pytest.raises(SandboxLifecycleError, match="LEGACY_OWNER_UNCERTAIN"):
        await (service.emit(event("new")) if operation == "emit" else service.replay_spool())
    assert await asyncio.to_thread(service.lock_path.read_bytes) == sentinel
    if spool_present:
        assert await asyncio.to_thread(service.spool_path.read_bytes) == original
    else:
        assert not await asyncio.to_thread(service.spool_path.exists)


# Layer: integration
async def test_dead_letter_success_then_unlink_failure_retains_both_effects(tmp_path, monkeypatch):
    service = SandboxLifecycleEventService(repository=await failed_repository(tmp_path), spool_path=tmp_path / "events.jsonl",
                                           max_replay_attempts=1)
    assert await service.emit(event("retained")) == "fallback"
    original, unlink = await asyncio.to_thread(service.spool_path.read_bytes), Path.unlink

    def refuse_commit(path, *args, **kwargs):
        if path == service.spool_path:
            raise OSError("controlled spool commit refusal")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "unlink", refuse_commit)
        with pytest.raises(OSError, match="controlled spool commit refusal"):
            await service.replay_spool()
    assert await asyncio.to_thread(service.spool_path.read_bytes) == original
    assert len(await spool_records(service.dead_letter_path)) == 1
    assert (await service.replay_spool()).dead_lettered == 1
    # The two outputs are not one transaction; replay can duplicate retained dead-letter evidence.
    assert len(await spool_records(service.dead_letter_path)) == 2
    assert not await asyncio.to_thread(service.spool_path.exists)


# Layer: integration
async def test_malformed_row_releases_owner_and_preserves_spool(tmp_path):
    repository = AsyncSandboxLifecycleRepository(tmp_path / "events.db")
    service = SandboxLifecycleEventService(repository=repository, spool_path=tmp_path / "events.jsonl")
    await asyncio.to_thread(service.spool_path.write_text, "{invalid\n", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        await service.replay_spool()
    assert await asyncio.to_thread(service.spool_path.read_text, encoding="utf-8") == "{invalid\n"
    await service._append_spool(event("retained"))
    assert "retained" in await asyncio.to_thread(service.spool_path.read_text, encoding="utf-8")
    assert await repository.list_events() == []


# Layer: integration
async def test_read_failure_does_not_become_empty_spool(tmp_path, monkeypatch):
    repository = AsyncSandboxLifecycleRepository(tmp_path / "events.db")
    service = SandboxLifecycleEventService(repository=repository, spool_path=tmp_path / "events.jsonl")
    await service._append_spool(event("retained"))
    original, native_open, streams = await asyncio.to_thread(service.spool_path.read_bytes), Path.open, []

    def fail_read(path, *args, **kwargs):
        stream = native_open(path, *args, **kwargs)
        if path == service.spool_path:
            streams.append(stream)
            readlines = stream.readlines

            def failed_readlines():
                readlines()
                raise FileNotFoundError("controlled read refusal after open")

            stream.readlines = failed_readlines
        return stream

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "open", fail_read)
        with pytest.raises(FileNotFoundError, match="controlled read refusal"):
            await service.replay_spool()
    assert streams and all(stream.closed for stream in streams)
    assert await asyncio.to_thread(service.spool_path.read_bytes) == original
    assert (await service.replay_spool()).replayed == 1
