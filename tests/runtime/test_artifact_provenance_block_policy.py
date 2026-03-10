from __future__ import annotations

import pytest

from orket.runtime.artifact_provenance_block_policy import (
    artifact_provenance_block_policy_snapshot,
    validate_artifact_provenance_block_policy,
)


# Layer: unit
def test_artifact_provenance_block_policy_snapshot_contains_expected_fields() -> None:
    payload = artifact_provenance_block_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    assert payload["enforcement_mode"] == "strict_block"
    required_fields = set(payload["required_provenance_fields"])
    assert "run_id" in required_fields
    assert "truth_classification" in required_fields


# Layer: contract
def test_validate_artifact_provenance_block_policy_accepts_current_snapshot() -> None:
    fields = validate_artifact_provenance_block_policy()
    assert "run_id" in fields


# Layer: contract
def test_validate_artifact_provenance_block_policy_rejects_required_field_mismatch() -> None:
    payload = artifact_provenance_block_policy_snapshot()
    payload["required_provenance_fields"] = [field for field in payload["required_provenance_fields"] if field != "run_id"]
    with pytest.raises(ValueError, match="E_ARTIFACT_PROVENANCE_BLOCK_REQUIRED_FIELDS_MISMATCH"):
        _ = validate_artifact_provenance_block_policy(payload)
