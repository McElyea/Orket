"""Layer: contract. Immutable explicit credential decisions and strict expiry precedence."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from orket.core.contracts.kernel_credentials import (
    CredentialBinding,
    CredentialIssueInputs,
    CredentialObservation,
    CredentialRecord,
    credential_hash,
    credential_refusal,
)

pytestmark = pytest.mark.contract
NOW = datetime(2030, 1, 1, tzinfo=UTC)
BINDING = CredentialBinding("session", "proposal", "tool", "scope", "executor", "profile")
RECORD = CredentialRecord(
    "session", "proposal", "tool", "scope", "executor", "profile", "2030-01-01T00:00:01Z", False, False, ""
)


def test_credential_hmac_is_repeatable_with_known_algorithm_vector_and_hidden_input_repr():
    inputs = CredentialIssueInputs(observed_at=NOW, hmac_key=b"key", raw_token="private-fixture", token_id="fixture-id")
    expected = "f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8"
    assert credential_hash("The quick brown fox jumps over the lazy dog", inputs) == expected
    assert credential_hash("The quick brown fox jumps over the lazy dog", inputs) == expected
    assert all(value not in repr(inputs) for value in ("private-fixture", "fixture-id", "b'key'"))
    with pytest.raises(FrozenInstanceError):
        inputs.hmac_key = b"changed"


@pytest.mark.parametrize(
    "field",
    [
        "session_id",
        "proposal_digest",
        "tool_name",
        "scope_digest",
        "executor_instance_id",
        "expected_tool_profile_digest",
    ],
)
def test_binding_refusal_precedes_expiry(field):
    inputs = CredentialObservation(observed_at=NOW + timedelta(days=1), hmac_key=b"fixture")
    assert credential_refusal(RECORD, replace(BINDING, **{field: "wrong"}), inputs) == "TOKEN_INVALID"


@pytest.mark.parametrize(
    ("changes", "seconds", "expected"),
    [
        ({}, 0, ""),
        ({}, 1, "TOKEN_EXPIRED"),
        ({"used": True}, 0, "TOKEN_REPLAY"),
        ({"used": True}, 1, "TOKEN_EXPIRED"),
        ({"invalidated": True, "invalidation_reason": "used"}, 0, "TOKEN_REPLAY"),
        ({"invalidated": True, "invalidation_reason": "expired"}, 0, "TOKEN_EXPIRED"),
        ({"invalidated": True, "invalidation_reason": "session_ended"}, 0, "TOKEN_INVALID"),
        ({"expires_at": ""}, 0, "TOKEN_EXPIRED"),
        ({"expires_at": "malformed"}, 0, "TOKEN_EXPIRED"),
        ({"expires_at": "2030-01-01T00:00:01"}, 0, ""),
    ],
)
def test_explicit_expiry_and_replay_decisions_repeat(changes, seconds, expected):
    record = replace(RECORD, **changes)
    inputs = CredentialObservation(observed_at=NOW + timedelta(seconds=seconds), hmac_key=b"fixture")
    assert credential_refusal(record, BINDING, inputs) == credential_refusal(record, BINDING, inputs) == expected


def test_observations_normalize_aware_time_and_refuse_naive_or_mutable_values():
    inputs = CredentialObservation(observed_at=NOW.astimezone(timezone(timedelta(hours=3))), hmac_key=b"fixture")
    assert inputs.observed_at == NOW and inputs.observed_at.tzinfo is UTC
    with pytest.raises(ValueError, match="REQUIRES_TIMEZONE"):
        CredentialObservation(observed_at=NOW.replace(tzinfo=None), hmac_key=b"fixture")
    with pytest.raises(ValueError, match="KEY_REQUIRED"):
        CredentialObservation(observed_at=NOW, hmac_key=bytearray(b"fixture"))
    with pytest.raises(ValueError, match="VALUE_INVALID"):
        replace(BINDING, scope_digest=[])
    with pytest.raises(ValueError, match="VALUE_INVALID"):
        replace(RECORD, used=1)
