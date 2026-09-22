"""Layer: integration. Explicit observation time at actual memory storage boundaries."""
import asyncio
from datetime import UTC, datetime, timedelta, timezone

import pytest

from orket.services.memory_store import MemoryStore
from orket.services.scoped_memory_store import ScopedMemoryStore
from tests.helpers.memory_state_probe import MemorySQLProbe, labeled, rows, writer_lock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class Clock:
    def __init__(self, now):
        self.now = now
        self.calls = 0

    def utc_now(self):
        self.calls += 1
        return self.now


@pytest.mark.parametrize("scope", ["project", "session", "episodic", "profile"])
async def test_memory_write_time_is_captured_before_initialization_wait(tmp_path, monkeypatch, scope):
    path = tmp_path / "memory.db"
    clock = Clock(datetime(2030, 1, 1, 15, 30, 10, 1234, tzinfo=timezone(timedelta(hours=3))))
    store = (MemoryStore if scope == "project" else ScopedMemoryStore)(path, runtime_inputs=clock)
    async with writer_lock(path) as blocker:
        probe = MemorySQLProbe(monkeypatch, ["time"], prefixes=("CREATE TABLE", "BEGIN IMMEDIATE"))
        if scope == "project":
            operation = store.remember("captured time")
        else:
            arguments = dict(key="companion_setting.theme", value="captured time")
            if scope != "profile":
                arguments["session_id"] = "session"
            operation = getattr(store, "write_" + scope)(**arguments)
        task = asyncio.create_task(labeled("time", operation))
        try:
            await probe.wait("time")
            clock.now += timedelta(days=1)
        finally:
            await blocker.rollback()
            await asyncio.wait_for(task, 10)
    table = {"project": "project_memory", "episodic": "extension_episodic_memory"}.get(scope, "extension_memory")
    assert await rows(path, f"SELECT created_at FROM {table}") == [("2030-01-01 12:30:10",)]
    assert clock.calls == 1
    if scope != "project":
        assert await rows(path, f"SELECT updated_at FROM {table}") == [("2030-01-01 12:30:10",)]
    await probe.assert_closed()


async def test_search_captures_one_observation_for_all_rows_before_sqlite_wait(tmp_path, monkeypatch):
    path = tmp_path / "memory.db"
    initial = MemoryStore(path)
    for content in ("first note", "second note"):
        await initial.remember(content, {"stale_at": "2030-01-01T00:00:00Z"})
    clock = Clock(datetime(2030, 1, 1, tzinfo=UTC))
    store = MemoryStore(path, runtime_inputs=clock)
    async with writer_lock(path) as blocker:
        probe = MemorySQLProbe(monkeypatch, ["search"])
        task = asyncio.create_task(labeled("search", store.search("note")))
        try:
            await probe.wait("search")
            clock.now += timedelta(seconds=1)
        finally:
            await blocker.rollback()
            result = await asyncio.wait_for(task, 10)
    assert len(result) == 2 and {row["trust_level"] for row in result} == {"advisory"}
    assert clock.calls == 1
    assert {row["trust_level"] for row in await store.search("note")} == {"stale_risk"}
    assert clock.calls == 2
    await probe.assert_closed()
