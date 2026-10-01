"""Integration: initializer admission owns real metadata, migrations and worker closure."""
from __future__ import annotations

import asyncio

import pytest

from tests.helpers.governed_read_ownership import interrupt_held_read
from tests.helpers.outward_store_ownership import STORES, TABLES, NativeStoreProbe, state
from tests.helpers.runtime_verification_hold import wait_entered

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("family", ["runs", "approvals", "events"])
@pytest.mark.parametrize("phase", ["connect", "wal", "begin", "schema", "commit", "close"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_initializer_retains_complete_native_attempt(tmp_path, monkeypatch, record_property, family, phase, mode):
    path = tmp_path / "selected.sqlite3"
    store = STORES[family](path)
    probe = NativeStoreProbe(monkeypatch, path, phase)
    task, waiter = asyncio.create_task(store.ensure_initialized()), None
    try:
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "sibling.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await waiter
        await probe.assert_settled()
        assert (await state(path))[TABLES[family]] == 0
        opened = len(probe.connections)
        await store.ensure_initialized()
        assert len(probe.connections) == opened, "settled initialization was not cached"
    finally:
        await probe.cleanup(task, waiter)


@pytest.mark.parametrize("family", ["runs", "approvals"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_initializer_owns_parent_directory_before_schema(tmp_path, monkeypatch, record_property, family, mode):
    path = tmp_path / "new-parent" / "selected.sqlite3"
    store = STORES[family](path)
    probe = NativeStoreProbe(monkeypatch, path, "mkdir")
    task, waiter = asyncio.create_task(store.ensure_initialized()), None
    try:
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "sibling.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await waiter
        await probe.assert_settled()
        assert (await state(path))[TABLES[family]] == 0
    finally:
        await probe.cleanup(task, waiter)


@pytest.mark.parametrize("family", ["runs", "approvals", "events"])
async def test_initializer_rebinding_cannot_poison_same_store_cache(tmp_path, monkeypatch, family):
    path, other = tmp_path / "selected.sqlite3", tmp_path / "other.sqlite3"
    store = STORES[family](path)
    probe = NativeStoreProbe(monkeypatch, path, "connect")
    task = asyncio.create_task(store.ensure_initialized())
    try:
        await wait_entered(probe)
        store.db_path = other
        probe.release.set()
        await task
        await probe.assert_settled()
        assert not await asyncio.to_thread(other.exists)
        assert (await state(path))[TABLES[family]] == 0
        await store.ensure_initialized()
        assert (await state(other))[TABLES[family]] == 0
    finally:
        await probe.cleanup(task)


@pytest.mark.parametrize("family", ["runs", "approvals", "events"])
async def test_initializer_lock_retains_admission_until_interrupted_attempt_closes(
    tmp_path, monkeypatch, record_property, family,
):
    path = tmp_path / "selected.sqlite3"
    store = STORES[family](path)
    probe = NativeStoreProbe(monkeypatch, path, "close")
    first, second = asyncio.create_task(store.ensure_initialized()), None
    started = asyncio.Event()

    async def again():
        started.set()
        await store.ensure_initialized()

    try:
        await interrupt_held_read(first, probe, "cancel", tmp_path / "sibling.sqlite3", record_property)
        second = asyncio.create_task(again())
        await asyncio.wait_for(started.wait(), 2)
        assert not second.done() and len(probe.connections) == 1
        probe.release.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        await second
        assert len(probe.connections) == 1
        await probe.assert_settled()
    finally:
        await probe.cleanup(first, second)


@pytest.mark.parametrize("family", ["runs", "approvals", "events"])
@pytest.mark.parametrize("phase", ["commit", "close"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_initializer_retains_native_failure_and_durable_migration(
    tmp_path, monkeypatch, record_property, family, phase, mode,
):
    path = tmp_path / "selected.sqlite3"
    store, failure = STORES[family](path), OSError("initializer acknowledgement failed")
    probe = NativeStoreProbe(monkeypatch, path, phase, failure=failure)
    task, waiter = asyncio.create_task(store.ensure_initialized()), None
    try:
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "sibling.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(OSError) as observed:
            await waiter
        assert observed.value is failure
        await probe.assert_settled()
        assert (await state(path))[TABLES[family]] == 0
        opened = len(probe.connections)
        await store.ensure_initialized()
        assert len(probe.connections) == opened + 1, "failed initialization was cached as successful"
        await probe.assert_settled()
    finally:
        await probe.cleanup(task, waiter)
