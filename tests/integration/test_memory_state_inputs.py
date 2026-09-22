"""Layer: integration. Captured memory input through native SQLite and application waits."""
from __future__ import annotations

import asyncio
import json

import pytest

from orket.application.services.extension_runtime_service import ExtensionRuntimeService
from orket.services.memory_store import MemoryStore
from orket.services.scoped_memory_store import ScopedMemoryStore
from tests.application.test_extension_runtime_service import _FakeModelProvider
from tests.helpers.memory_state_probe import MemorySQLProbe, labeled, rows, writer_lock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("scope", ["project", "session", "episodic", "profile"])
async def test_memory_captures_nested_metadata_before_native_initialization_wait(tmp_path, monkeypatch, scope):
    path = tmp_path / "memory.db"
    store = MemoryStore(path) if scope == "project" else ScopedMemoryStore(path)
    metadata = {"nested": {"values": ["captured"]}}
    async with writer_lock(path) as blocker:
        probe = MemorySQLProbe(monkeypatch, ["write"], prefixes=("CREATE TABLE", "BEGIN IMMEDIATE"))
        if scope == "project":
            operation = store.remember("captured content", metadata)
        elif scope == "profile":
            operation = store.write_profile(key="companion_setting.theme", value="captured content", metadata=metadata)
        else:
            operation = getattr(store, "write_" + scope)(session_id="session", key="topic", value="captured content", metadata=metadata)
        task = asyncio.create_task(labeled("write", operation))
        try:
            await probe.wait("write")
            metadata["nested"]["values"].append("MUTATED")
        finally:
            await blocker.rollback()
            await asyncio.wait_for(task, 10)
    table = {"project": "project_memory", "episodic": "extension_episodic_memory"}.get(scope, "extension_memory")
    result, = await rows(path, f"SELECT metadata_json FROM {table}")
    await probe.assert_closed()
    assert json.loads(result[0])["nested"]["values"] == ["captured"]


async def test_project_memory_binds_relative_database_before_cwd_rotation(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.chdir(first)
    store = MemoryStore("memory.db")
    monkeypatch.chdir(second)
    await store.remember("bound to admitted database", {"source": "first"})
    assert (first / "memory.db").exists()
    assert not (second / "memory.db").exists()
    result, = await rows(first / "memory.db", "SELECT content FROM project_memory")
    assert result == ("bound to admitted database",)


@pytest.mark.parametrize("scope", ["session_memory", "episodic_memory"])
async def test_extension_memory_captures_nested_metadata_before_session_admission(tmp_path, scope):
    store = ScopedMemoryStore(tmp_path / "memory.db")
    service = ExtensionRuntimeService(project_root=tmp_path, memory_store=store, model_provider=_FakeModelProvider())
    metadata = {"nested": {"values": ["captured"]}}
    entered = asyncio.Event()
    original = service._record_active_session

    async def observe(*args):
        entered.set()
        await original(*args)

    service._record_active_session = observe
    await service._state_lock.acquire()
    task = asyncio.create_task(service.memory_write(extension_id="capture", scope=scope,
        session_id="session", key="topic", value="captured", metadata=metadata))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        metadata["nested"]["values"].append("MUTATED")
    finally:
        service._state_lock.release()
        result = await asyncio.wait_for(task, 10)
        await service.close()
    assert result["record"]["metadata"]["nested"]["values"] == ["captured"]
    table = "extension_memory" if scope == "session_memory" else "extension_episodic_memory"
    stored, = await rows(tmp_path / "memory.db", f"SELECT metadata_json FROM {table}")
    assert json.loads(stored[0])["nested"]["values"] == ["captured"]
