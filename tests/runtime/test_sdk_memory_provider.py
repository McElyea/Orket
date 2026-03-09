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
            key="companion_setting.display_name",
            value="Companion",
        )
    )
    assert write.ok is True

    query = provider.query(
        MemoryQueryRequest(scope="profile_memory", session_id="session-b", query="display_name", limit=10)
    )
    assert query.ok is True
    assert len(query.records) == 1
    assert query.records[0].value == "Companion"


def test_sqlite_memory_provider_profile_scope_enforces_fact_confirmation(tmp_path: Path) -> None:
    """Layer: integration. Verifies profile writes require confirmation metadata for user-fact keys."""
    provider = SQLiteMemoryCapabilityProvider(tmp_path / "memory.db")
    unconfirmed = provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="user_fact.name",
            value="Aster",
        )
    )
    assert unconfirmed.ok is False
    assert unconfirmed.error_code == "E_PROFILE_MEMORY_CONFIRMATION_REQUIRED"

    confirmed = provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="user_fact.name",
            value="Aster",
            metadata={"user_confirmed": True},
        )
    )
    assert confirmed.ok is True


def test_sqlite_memory_provider_profile_scope_supports_listing_and_exact_key_query(tmp_path: Path) -> None:
    """Layer: integration. Verifies deterministic profile listing and exact-key query behavior."""
    provider = SQLiteMemoryCapabilityProvider(tmp_path / "memory.db")
    assert provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="user_preference.theme",
            value="dark",
        )
    ).ok
    assert provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="companion_setting.role_id",
            value="strategist",
        )
    ).ok

    listed = provider.query(MemoryQueryRequest(scope="profile_memory", query="", limit=10))
    assert listed.ok is True
    assert [row.key for row in listed.records] == ["companion_setting.role_id", "user_preference.theme"]

    exact = provider.query(
        MemoryQueryRequest(scope="profile_memory", query="key:companion_setting.role_id", limit=10)
    )
    assert exact.ok is True
    assert len(exact.records) == 1
    assert exact.records[0].value == "strategist"
