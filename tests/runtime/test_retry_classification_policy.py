from __future__ import annotations

import pytest

from orket.runtime.retry_classification_policy import (
    retry_classification_policy_snapshot,
    validate_retry_classification_policy,
)


# Layer: unit
def test_retry_classification_policy_snapshot_contains_expected_signals() -> None:
    payload = retry_classification_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    assert payload["projection_only"] is True
    assert payload["projection_source"] == "retry_classification_rules"
    assert payload["attempt_history_authoritative"] is False
    signals = {row["signal"] for row in payload["rows"]}
    assert "model_timeout_retry" in signals
    assert "unexpected_runtime_exception" in signals


# Layer: contract
def test_validate_retry_classification_policy_accepts_current_snapshot() -> None:
    signals = validate_retry_classification_policy()
    assert "model_connection_retry" in signals


# Layer: contract
def test_validate_retry_classification_policy_rejects_dangerous_retry_count() -> None:
    payload = retry_classification_policy_snapshot()
    payload["rows"][2]["max_attempts"] = 2
    with pytest.raises(ValueError, match="E_RETRY_POLICY_DANGEROUS_RETRY_COUNT:openai_http_status_error"):
        _ = validate_retry_classification_policy(payload)


# Layer: contract
def test_validate_retry_classification_policy_rejects_attempt_history_authority_claim() -> None:
    payload = retry_classification_policy_snapshot()
    payload["attempt_history_authoritative"] = True
    with pytest.raises(ValueError, match="E_RETRY_POLICY_ATTEMPT_AUTHORITY_INVALID"):
        _ = validate_retry_classification_policy(payload)


# Layer: contract
def test_validate_retry_classification_policy_rejects_empty_payload_instead_of_falling_back() -> None:
    with pytest.raises(ValueError, match="E_RETRY_POLICY_SCHEMA_VERSION_INVALID"):
        _ = validate_retry_classification_policy({})


# Layer: contract
@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_error"),
    [
        ("schema_version", "999.0", "E_RETRY_POLICY_SCHEMA_VERSION_INVALID"),
        ("projection_only", False, "E_RETRY_POLICY_PROJECTION_ONLY_INVALID"),
        ("projection_source", "runtime_attempt_history", "E_RETRY_POLICY_PROJECTION_SOURCE_INVALID"),
    ],
)
def test_validate_retry_classification_policy_rejects_projection_framing_drift(
    field_name: str,
    field_value: object,
    expected_error: str,
) -> None:
    payload = retry_classification_policy_snapshot()
    payload[field_name] = field_value

    with pytest.raises(ValueError, match=expected_error):
        _ = validate_retry_classification_policy(payload)
