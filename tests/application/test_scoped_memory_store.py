from __future__ import annotations

from pathlib import Path

import pytest

from orket.services.profile_write_policy import ProfileWritePolicyError
from orket.services.scoped_memory_store import ScopedMemoryStore


@pytest.mark.asyncio
async def test_scoped_memory_store_isolates_session_scope_and_clear_session(tmp_path: Path) -> None:
    """Layer: integration. Verifies session memory is isolated per session and clear_session is scope-safe."""
    store = ScopedMemoryStore(tmp_path / "memory.db")
    await store.write_session(session_id="session-a", key="topic", value="orchestration")
    await store.write_session(session_id="session-b", key="topic", value="testing")

    rows_a = await store.query_session(session_id="session-a", query="", limit=10)
    assert len(rows_a) == 1
    assert rows_a[0].value == "orchestration"

    deleted = await store.clear_session(session_id="session-a")
    assert deleted == 1
    assert await store.query_session(session_id="session-a", query="", limit=10) == []
    rows_b = await store.query_session(session_id="session-b", query="", limit=10)
    assert len(rows_b) == 1
    assert rows_b[0].value == "testing"


@pytest.mark.asyncio
async def test_scoped_memory_store_profile_access_patterns_are_deterministic(tmp_path: Path) -> None:
    """Layer: integration. Verifies profile upsert/read/list/query access patterns remain deterministic."""
    store = ScopedMemoryStore(tmp_path / "memory.db")
    await store.write_profile(key="user_preference.theme", value="dark", metadata={})
    await store.write_profile(key="companion_setting.role_id", value="tutor", metadata={})
    await store.write_profile(key="companion_setting.role_id", value="strategist", metadata={})

    role = await store.read_profile(key="companion_setting.role_id")
    assert role is not None
    assert role.value == "strategist"

    listed = await store.list_profile(limit=10)
    assert [row.key for row in listed] == ["companion_setting.role_id", "user_preference.theme"]

    queried = await store.query_profile(query="dark", limit=10)
    assert len(queried) == 1
    assert queried[0].key == "user_preference.theme"


@pytest.mark.asyncio
async def test_scoped_memory_store_enforces_profile_write_policy(tmp_path: Path) -> None:
    """Layer: integration. Verifies profile write policy blocks unconfirmed user-fact writes."""
    store = ScopedMemoryStore(tmp_path / "memory.db")
    with pytest.raises(ProfileWritePolicyError, match="E_PROFILE_MEMORY_CONFIRMATION_REQUIRED"):
        await store.write_profile(key="user_fact.name", value="Aster", metadata={})
