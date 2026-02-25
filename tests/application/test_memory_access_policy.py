from __future__ import annotations

import pytest

from orket.application.services.memory_access_policy import (
    MemoryAccessPolicyError,
    enforce_role_access,
    normalize_retrieval_rows,
    resolve_utility_agent_profile,
)


def test_resolve_utility_agent_profile_unknown_raises() -> None:
    with pytest.raises(MemoryAccessPolicyError) as exc:
        resolve_utility_agent_profile("unknown-profile")
    assert exc.value.code == "E_UTILITY_AGENT_PROFILE_UNKNOWN"


def test_enforce_role_access_rejects_forbidden_role() -> None:
    profile = resolve_utility_agent_profile("ops_assistant")
    with pytest.raises(MemoryAccessPolicyError) as exc:
        enforce_role_access(role="coder", profile=profile)
    assert exc.value.code == "E_UTILITY_AGENT_ROLE_FORBIDDEN"
    payload = exc.value.to_payload()
    assert payload["ok"] is False
    assert payload["detail"]["profile_id"] == "ops_assistant"


def test_normalize_retrieval_rows_is_deterministic_across_input_order() -> None:
    rows_a = [
        {"content": "b", "metadata": {"i": 2}, "score": 1.0, "timestamp": "2026-02-24T10:00:00+00:00", "id": 7},
        {"content": "a", "metadata": {"i": 1}, "score": 2.0, "timestamp": "2026-02-24T09:00:00+00:00", "id": 4},
        {"content": "c", "metadata": {"i": 3}, "score": 1.0, "timestamp": "2026-02-24T11:00:00+00:00", "id": 8},
    ]
    rows_b = list(reversed(rows_a))
    normalized_a = normalize_retrieval_rows(rows_a, limit=3)
    normalized_b = normalize_retrieval_rows(rows_b, limit=3)

    assert normalized_a == normalized_b
    assert [row["content"] for row in normalized_a] == ["a", "b", "c"]
