from __future__ import annotations

from pathlib import Path

from orket.capabilities.sdk_memory_provider import SQLiteMemoryCapabilityProvider
from orket_extension_sdk.memory import MemoryQueryRequest, MemoryWriteRequest


def test_sqlite_memory_provider_writes_and_queries_session_scope(tmp_path: Path) -> None:
    """Layer: integration. Verifies session memory records are isolated by session id."""
    provider = SQLiteMemoryCapabilityProvider(tmp_path / "memory.db")
    first = provider.write(
        MemoryWriteRequest(
            scope="session_memory",
            session_id="session-a",
            key="topic",
            value="orchestration",
        )
    )
    second = provider.write(
        MemoryWriteRequest(
            scope="session_memory",
            session_id="session-b",
            key="topic",
            value="testing",
        )
    )
    assert first.ok is True
    assert second.ok is True

    query_a = provider.query(
        MemoryQueryRequest(scope="session_memory", session_id="session-a", query="topic", limit=10)
    )
    assert query_a.ok is True
    assert len(query_a.records) == 1
    assert query_a.records[0].value == "orchestration"


def test_sqlite_memory_provider_profile_scope_ignores_session_id(tmp_path: Path) -> None:
    """Layer: integration. Verifies profile memory is shared independent of session id input."""
    provider = SQLiteMemoryCapabilityProvider(tmp_path / "memory.db")
    write = provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            session_id="session-a",
            key="name",
            value="Companion",
        )
    )
    assert write.ok is True

    query = provider.query(
        MemoryQueryRequest(scope="profile_memory", session_id="session-b", query="name", limit=10)
    )
    assert query.ok is True
    assert len(query.records) == 1
    assert query.records[0].value == "Companion"
