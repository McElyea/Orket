"""Actual crash files, explicit observations, native ownership and worker lifetime."""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import UTC, datetime

import pytest

from orket.adapters.storage import crash_log_store as storage
from orket.adapters.storage.crash_log_store import CrashLogStore
from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.application.services.crash_report_service import CrashReportService
from orket.core.contracts.local_file_lock import LocalFileLockError

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
STAMP = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)


async def test_concurrent_distinct_roots_preserve_trace_and_explicit_clock(tmp_path):
    services = [CrashReportService(tmp_path / str(index), clock=lambda: STAMP) for index in range(2)]
    paths = await asyncio.gather(*(owner.publish(ValueError(str(index)), f"TRACE-{index}")
                                   for index, owner in enumerate(services)))
    for index, path in enumerate(paths):
        text = await asyncio.to_thread(path.read_text, encoding="utf-8")
        assert path == services[index].workspace / "orket_crash.log"
        assert STAMP.isoformat() in text and f"TRACE-{index}" in text
        assert f"TRACE-{1 - index}" not in text
        # Publication has no retained file handle; Windows also enforces this rename.
        await asyncio.to_thread(path.rename, path.with_suffix(".verified"))


async def test_append_and_rotation_keep_latest_records_in_order(tmp_path):
    store = CrashLogStore(tmp_path, max_bytes=8, backup_count=2)
    path = await store.append("one\n")
    await store.append("two\n")
    assert await asyncio.to_thread(path.read_bytes) == b"two\n"
    assert await asyncio.to_thread(path.with_suffix(".log.1").read_bytes) == b"one\n"
    await store.append("three\n")
    await store.append("four\n")
    assert await asyncio.to_thread(path.read_bytes) == b"four\n"
    assert await asyncio.to_thread(path.with_suffix(".log.1").read_bytes) == b"three\n"
    assert await asyncio.to_thread(path.with_suffix(".log.2").read_bytes) == b"two\n"
    assert not await asyncio.to_thread(path.with_suffix(".log.3").exists)


async def test_unicode_append_preserves_prior_content_and_oversized_record(tmp_path):
    store = CrashLogStore(tmp_path, max_bytes=20)
    path = await store.append("first\n")
    await store.append("second\n")
    assert await asyncio.to_thread(path.read_text, encoding="utf-8") == "first\nsecond\n"
    text = "diagnostic \u2603\n" * 5
    await store.append(text)
    assert await asyncio.to_thread(path.read_text, encoding="utf-8") == text
    assert await asyncio.to_thread(path.with_suffix(".log.1").read_text, encoding="utf-8") == "first\nsecond\n"


@pytest.mark.parametrize("name", ["orket_crash.log", "orket_crash.log.1"])
async def test_non_file_destinations_refuse_without_altering_prior_bytes(tmp_path, name):
    await asyncio.to_thread((tmp_path / name).mkdir)
    if name != "orket_crash.log":
        await asyncio.to_thread((tmp_path / "orket_crash.log").write_text, "original", encoding="utf-8")
    with pytest.raises(ValueError, match="E_CRASH_LOG_NOT_REGULAR"):
        await CrashLogStore(tmp_path).append("new\n")
    if name != "orket_crash.log":
        assert await asyncio.to_thread((tmp_path / "orket_crash.log").read_text, encoding="utf-8") == "original"


async def test_busy_native_owner_refuses_then_released_owner_can_append(tmp_path):
    target = tmp_path / "orket_crash.log"
    locks = NativeFileLocks(target, suffix=".owners", error_prefix="E_CRASH", empty_key_error="E_CRASH_KEY")
    async with locks.hold("append"):
        with pytest.raises(LocalFileLockError, match="owner_busy"):
            await CrashLogStore(tmp_path).append("refused\n")
        assert not await asyncio.to_thread(target.exists)
    path = await CrashLogStore(tmp_path).append("admitted\n")
    assert await asyncio.to_thread(path.read_bytes) == b"admitted\n"


async def test_readback_mismatch_is_not_publication_success(tmp_path, monkeypatch):
    append = storage._append_bytes

    def alter_after_write(path, payload):
        append(path, payload)
        path.write_bytes(b"x" * len(payload))

    monkeypatch.setattr(storage, "_append_bytes", alter_after_write)
    with pytest.raises(OSError, match="E_CRASH_LOG_UNVERIFIED"):
        await CrashLogStore(tmp_path).append("expected\n")
    assert await asyncio.to_thread((tmp_path / "orket_crash.log").read_bytes) == b"x" * 9


@pytest.mark.parametrize("interrupt", ["cancel", "timeout"])
async def test_interruption_retains_actual_append_verification_and_lock(tmp_path, monkeypatch, interrupt):
    entered, release = threading.Event(), threading.Event()
    append = storage._append_bytes

    def held(path, payload):
        entered.set()
        assert release.wait(5)
        append(path, payload)

    async def invoke():
        if interrupt == "timeout":
            async with asyncio.timeout(0.1):
                await CrashReportService(tmp_path, clock=lambda: STAMP).publish(ValueError(), "HELD_TRACE")
        else:
            await CrashReportService(tmp_path, clock=lambda: STAMP).publish(ValueError(), "HELD_TRACE")

    monkeypatch.setattr(storage, "_append_bytes", held)
    task = asyncio.create_task(invoke())
    try:
        started = time.monotonic()
        assert await asyncio.to_thread(entered.wait, 0.5)
        assert time.monotonic() - started < 0.5
        if interrupt == "cancel":
            task.cancel()
        await asyncio.sleep(0.15)
        assert not task.done() and not await asyncio.to_thread((tmp_path / "orket_crash.log").exists)
        with pytest.raises(LocalFileLockError, match="owner_busy"):
            await CrashLogStore(tmp_path).append("refused")
        released = time.monotonic()
        release.set()
        with pytest.raises(asyncio.CancelledError if interrupt == "cancel" else TimeoutError):
            await asyncio.wait_for(task, 3)
        assert time.monotonic() - released < 3
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert "HELD_TRACE" in await asyncio.to_thread((tmp_path / "orket_crash.log").read_text, encoding="utf-8")
    await CrashLogStore(tmp_path).append("NEXT\n")


async def test_capture_root_and_time_before_worker_can_be_retargeted(tmp_path, monkeypatch):
    initial, later = tmp_path / "selected", tmp_path / "later"
    await asyncio.to_thread(later.mkdir)
    times = [STAMP]
    service = CrashReportService(initial, clock=lambda: times[0])
    append = storage._append_bytes

    def mutate_ambient_state(path, payload):
        times[0] = datetime(2030, 1, 1, tzinfo=UTC)
        monkeypatch.chdir(later)
        append(path, payload)

    monkeypatch.setattr(storage, "_append_bytes", mutate_ambient_state)
    path = await service.publish(RuntimeError(), "captured")
    assert path == initial / "orket_crash.log"
    assert STAMP.isoformat() in await asyncio.to_thread(path.read_text, encoding="utf-8")
    assert not await asyncio.to_thread(lambda: list(later.iterdir()))


async def test_worker_write_failure_survives_cancellation(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def fail_after_release(path, payload):
        entered.set()
        assert release.wait(5)
        raise OSError("fixture disk failure")

    monkeypatch.setattr(storage, "_append_bytes", fail_after_release)
    task = asyncio.create_task(CrashLogStore(tmp_path).append("record"))
    try:
        assert await asyncio.to_thread(entered.wait, 0.5)
        task.cancel()
        release.set()
        with pytest.raises(OSError, match="fixture disk failure"):
            await asyncio.wait_for(task, 3)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert not await asyncio.to_thread((tmp_path / "orket_crash.log").exists)
