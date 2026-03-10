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
