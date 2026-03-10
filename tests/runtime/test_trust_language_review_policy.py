from __future__ import annotations

import pytest

from orket.runtime.trust_language_review_policy import (
    classify_trust_language_phrase,
    trust_language_review_policy_snapshot,
    validate_trust_language_review_policy,
)


# Layer: unit
def test_trust_language_review_policy_snapshot_contains_expected_claims() -> None:
    payload = trust_language_review_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    claims = {row["claim"] for row in payload["claims"]}
    assert claims == {
        "saved",
        "synced",
        "used_memory",
        "searched",
        "verified",
    }


# Layer: contract
def test_validate_trust_language_review_policy_accepts_current_snapshot() -> None:
    claims = validate_trust_language_review_policy()
    assert "saved" in claims


# Layer: contract
def test_classify_trust_language_phrase_marks_unqualified_and_qualified_examples() -> None:
    assert classify_trust_language_phrase("saved") == "unqualified"
    assert classify_trust_language_phrase("saved with durable receipt") == "qualified"


# Layer: contract
def test_validate_trust_language_review_policy_rejects_claim_set_mismatch() -> None:
    payload = trust_language_review_policy_snapshot()
    payload["claims"] = [row for row in payload["claims"] if row["claim"] != "verified"]
    with pytest.raises(ValueError, match="E_TRUST_LANGUAGE_REVIEW_POLICY_CLAIM_SET_MISMATCH"):
        _ = validate_trust_language_review_policy(payload)
