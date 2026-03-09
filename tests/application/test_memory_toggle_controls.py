from __future__ import annotations

from pathlib import Path

from orket.capabilities.sdk_memory_provider import SQLiteMemoryCapabilityProvider
from orket.services.scoped_memory_store import MemoryControls
from orket_extension_sdk.memory import MemoryQueryRequest, MemoryWriteRequest


def test_memory_controls_disable_session_scope_reads_and_writes(tmp_path: Path) -> None:
    """Layer: integration. Verifies session-memory toggles fail closed for write/query operations."""
    provider = SQLiteMemoryCapabilityProvider(
        tmp_path / "memory.db",
        controls=MemoryControls(session_memory_enabled=False, profile_memory_enabled=True),
    )
    write = provider.write(
        MemoryWriteRequest(scope="session_memory", session_id="s1", key="topic", value="hello")
    )
    assert write.ok is False
    assert write.error_code == "memory_session_disabled"

    query = provider.query(MemoryQueryRequest(scope="session_memory", session_id="s1", query="", limit=10))
    assert query.ok is False
    assert query.error_code == "memory_session_disabled"


def test_memory_controls_disable_profile_scope_reads_and_writes(tmp_path: Path) -> None:
    """Layer: integration. Verifies profile-memory toggles fail closed for write/query operations."""
    provider = SQLiteMemoryCapabilityProvider(
        tmp_path / "memory.db",
        controls=MemoryControls(session_memory_enabled=True, profile_memory_enabled=False),
    )
    write = provider.write(
        MemoryWriteRequest(scope="profile_memory", key="companion_setting.role_id", value="tutor")
    )
    assert write.ok is False
    assert write.error_code == "memory_profile_disabled"

    query = provider.query(MemoryQueryRequest(scope="profile_memory", query="", limit=10))
    assert query.ok is False
    assert query.error_code == "memory_profile_disabled"


def test_clear_session_does_not_delete_profile_scope_records(tmp_path: Path) -> None:
    """Layer: integration. Verifies clear_session removes only session-memory rows."""
    provider = SQLiteMemoryCapabilityProvider(tmp_path / "memory.db")
    provider.write(
        MemoryWriteRequest(scope="session_memory", session_id="session-a", key="topic", value="orchestration")
    )
    provider.write(
        MemoryWriteRequest(scope="session_memory", session_id="session-b", key="topic", value="testing")
    )
    provider.write(
        MemoryWriteRequest(scope="profile_memory", key="companion_setting.role_id", value="strategist")
    )

    deleted = provider.clear_session("session-a")
    assert deleted == 1

    rows_a = provider.query(
        MemoryQueryRequest(scope="session_memory", session_id="session-a", query="", limit=10)
    ).records
    rows_b = provider.query(
        MemoryQueryRequest(scope="session_memory", session_id="session-b", query="", limit=10)
    ).records
    profile_rows = provider.query(MemoryQueryRequest(scope="profile_memory", query="", limit=10)).records
    assert rows_a == []
    assert len(rows_b) == 1
    assert len(profile_rows) == 1
    assert profile_rows[0].key == "companion_setting.role_id"
