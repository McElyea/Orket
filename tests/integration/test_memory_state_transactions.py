"""Layer: integration. Native writer contention and independent durable memory observations."""
from __future__ import annotations

import asyncio
import json

import pytest

from orket.services.memory_store import MemoryStore
from orket.services.profile_write_policy import ProfileWritePolicyError
from orket.services.scoped_memory_store import ScopedMemoryStore
from tests.helpers.memory_state_probe import MemorySQLProbe, labeled, rows, writer_lock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("key", ["user_fact.name", "ext:fixture:user_fact.name"])
async def test_concurrent_first_facts_evaluate_policy_under_one_writer(tmp_path, monkeypatch, key):
    path = tmp_path / "memory.db"
    stores = [ScopedMemoryStore(path), ScopedMemoryStore(path)]
    for store in stores:
        await store.ensure_initialized()
    async with writer_lock(path) as blocker:
        probe = MemorySQLProbe(monkeypatch, ["Aster", "Nova"])
        tasks = [asyncio.create_task(labeled(value, store.write_profile(key=key, value=value,
            metadata={"user_confirmed": True}))) for store, value in zip(stores, ("Aster", "Nova"), strict=True)]
        try:
            await asyncio.gather(probe.wait("Aster"), probe.wait("Nova"))
        finally:
            await blocker.rollback()
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 10)
    stored, = await rows(path, "SELECT memory_value, metadata_json FROM extension_memory WHERE memory_key=?", (key,))
    await probe.assert_closed()
    successes = [result for result in results if not isinstance(result, BaseException)]
    failures = [result for result in results if isinstance(result, BaseException)]
    assert len(successes) == len(failures) == 1, (results, probe.statements)
    assert isinstance(failures[0], ProfileWritePolicyError)
    assert failures[0].code == "E_PROFILE_MEMORY_CONTRADICTION_REQUIRES_CORRECTION"
    assert successes[0].value == stored[0]
    assert json.loads(stored[1])["write_threshold"] == "confirmed_user_fact"


async def test_namespaced_fact_requires_correction_without_losing_scope_identity(tmp_path):
    path = tmp_path / "memory.db"
    store = ScopedMemoryStore(path)
    key = "ext:fixture:user_fact.name"
    await store.write_profile(key=key, value="Aster", metadata={"user_confirmed": True})
    with pytest.raises(ProfileWritePolicyError, match="E_PROFILE_MEMORY_CONTRADICTION_REQUIRES_CORRECTION"):
        await store.write_profile(key=key, value="Nova", metadata={"user_confirmed": True})
    unchanged, = await rows(path, "SELECT memory_key, memory_value FROM extension_memory")
    assert unchanged == (key, "Aster")
    result = await store.write_profile(key=key, value="Nova", metadata={"user_confirmed": True, "user_correction": True})
    assert result.key == key and result.value == "Nova"
    assert result.metadata["conflict_resolution"] == "user_correction"
    assert result.metadata["write_threshold"] == "confirmed_user_fact"


async def test_same_value_cannot_regress_authoritative_observation_metadata(tmp_path):
    path = tmp_path / "memory.db"
    store = ScopedMemoryStore(path)
    metadata = {"observed_at": "2030-01-02T00:00:00+00:00", "nested": {"proof": "current"}}
    await store.write_profile(key="companion_setting.theme", value="dark", metadata=metadata)
    with pytest.raises(ProfileWritePolicyError, match="E_PROFILE_MEMORY_STALE_UPDATE"):
        await store.write_profile(key="companion_setting.theme", value="dark",
            metadata={"observed_at": "2030-01-01T00:00:00+00:00", "nested": {"proof": "stale"}})
    stored, = await rows(path, "SELECT metadata_json FROM extension_memory")
    assert json.loads(stored[0])["nested"]["proof"] == "current"


async def test_concurrent_project_duplicates_publish_one_consistent_fts_record(tmp_path, monkeypatch):
    path = tmp_path / "memory.db"
    stores = [MemoryStore(path), MemoryStore(path)]
    for store in stores:
        await store._ensure_initialized()
    async with writer_lock(path) as blocker:
        probe = MemorySQLProbe(monkeypatch, ["first", "second"])
        tasks = [asyncio.create_task(labeled(label, store.remember("same atomic memory", {"writer": label})))
                 for store, label in zip(stores, ("first", "second"), strict=True)]
        try:
            await asyncio.gather(probe.wait("first"), probe.wait("second"))
        finally:
            await blocker.rollback()
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 10)
    assert await rows(path, "SELECT COUNT(*) FROM project_memory") == [(1,)]
    assert await rows(path, "SELECT COUNT(*) FROM project_memory_fts") == [(1,)]
    await probe.assert_closed()
    assert results == [None, None], results
    assert len(await stores[0].search("atomic")) == 1
