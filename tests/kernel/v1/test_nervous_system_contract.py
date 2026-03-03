from __future__ import annotations

from orket.kernel.v1.nervous_system_contract import (
    COMMIT_STATUSES_V1,
    GENESIS_STATE_DIGEST,
    REASON_CODES_V1_ORDER,
    canonical_scope_digest,
    is_genesis_state_digest,
    ordered_reason_codes_v1,
    tool_profile_digest,
)


def test_genesis_state_digest_is_locked_zero_hash() -> None:
    assert GENESIS_STATE_DIGEST == "0" * 64
    assert is_genesis_state_digest("0" * 64)
    assert is_genesis_state_digest(("0" * 64).upper())
    assert not is_genesis_state_digest("1" * 64)


def test_commit_statuses_v1_are_locked() -> None:
    assert COMMIT_STATUSES_V1 == (
        "COMMITTED",
        "REJECTED_PRECONDITION",
        "REJECTED_POLICY",
        "REJECTED_APPROVAL_MISSING",
        "ERROR",
    )


def test_reason_codes_ordering_is_deterministic_and_deduplicated() -> None:
    ordered = ordered_reason_codes_v1(
        [
            "TOKEN_EXPIRED",
            "SCHEMA_INVALID",
            "TOKEN_EXPIRED",
            "APPROVAL_REQUIRED_EXFIL",
            "SCOPE_VIOLATION",
        ]
    )
    assert ordered == [
        "SCHEMA_INVALID",
        "SCOPE_VIOLATION",
        "APPROVAL_REQUIRED_EXFIL",
        "TOKEN_EXPIRED",
    ]


def test_reason_codes_unknown_values_are_sorted_after_known() -> None:
    ordered = ordered_reason_codes_v1(
        [
            "Z_UNKNOWN",
            "RESULT_SCHEMA_INVALID",
            "A_UNKNOWN",
        ]
    )
    assert ordered == [
        "RESULT_SCHEMA_INVALID",
        "A_UNKNOWN",
        "Z_UNKNOWN",
    ]


def test_scope_and_tool_profile_digests_use_canonical_json() -> None:
    scope_a = {"allow": ["email.read", "email.send"], "ttl_seconds": 300}
    scope_b = {"ttl_seconds": 300, "allow": ["email.read", "email.send"]}
    profile_a = {"tool": "send_email", "exfil": True, "risk": "high"}
    profile_b = {"risk": "high", "exfil": True, "tool": "send_email"}

    assert canonical_scope_digest(scope_a) == canonical_scope_digest(scope_b)
    assert tool_profile_digest(profile_a) == tool_profile_digest(profile_b)


def test_reason_codes_reference_is_locked() -> None:
    assert REASON_CODES_V1_ORDER == (
        "SCHEMA_INVALID",
        "POLICY_FORBIDDEN",
        "LEAK_DETECTED",
        "SCOPE_VIOLATION",
        "UNKNOWN_TOOL_PROFILE",
        "APPROVAL_REQUIRED_DESTRUCTIVE",
        "APPROVAL_REQUIRED_EXFIL",
        "APPROVAL_REQUIRED_CREDENTIALED",
        "TOKEN_INVALID",
        "TOKEN_EXPIRED",
        "TOKEN_REPLAY",
        "RESULT_SCHEMA_INVALID",
        "RESULT_LEAK_DETECTED",
    )
