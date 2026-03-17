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


def test_sqlite_memory_provider_profile_scope_requires_explicit_user_correction_for_fact_replacement(tmp_path: Path) -> None:
    """Layer: integration. Verifies contradicting durable user-fact writes fail closed without user-correction metadata."""
    provider = SQLiteMemoryCapabilityProvider(tmp_path / "memory.db")
    initial = provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="user_fact.name",
            value="Aster",
            metadata={"user_confirmed": True, "observed_at": "2026-03-17T14:00:00+00:00"},
        )
    )
    assert initial.ok is True

    contradicting = provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="user_fact.name",
            value="Nova",
            metadata={"user_confirmed": True, "observed_at": "2026-03-17T14:05:00+00:00"},
        )
    )
    assert contradicting.ok is False
    assert contradicting.error_code == "E_PROFILE_MEMORY_CONTRADICTION_REQUIRES_CORRECTION"

    corrected = provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="user_fact.name",
            value="Nova",
            metadata={
                "user_confirmed": True,
                "user_correction": True,
                "write_rationale": "user corrected the stored name",
                "observed_at": "2026-03-17T14:06:00+00:00",
            },
        )
    )
    assert corrected.ok is True

    exact = provider.query(MemoryQueryRequest(scope="profile_memory", query="key:user_fact.name", limit=10))
    assert exact.ok is True
    assert exact.records[0].value == "Nova"
    assert exact.records[0].metadata["trust_level"] == "authoritative"
    assert exact.records[0].metadata["conflict_resolution"] == "user_correction"


def test_sqlite_memory_provider_profile_scope_rejects_stale_setting_updates(tmp_path: Path) -> None:
    """Layer: integration. Verifies older durable-setting observations fail closed as stale updates."""
    provider = SQLiteMemoryCapabilityProvider(tmp_path / "memory.db")
    assert provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="companion_setting.role_id",
            value="strategist",
            metadata={"observed_at": "2026-03-17T14:00:00+00:00"},
        )
    ).ok

    stale = provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="companion_setting.role_id",
            value="planner",
            metadata={"observed_at": "2026-03-17T13:55:00+00:00"},
        )
    )
    assert stale.ok is False
    assert stale.error_code == "E_PROFILE_MEMORY_STALE_UPDATE"
