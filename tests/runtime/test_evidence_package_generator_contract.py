from __future__ import annotations

import pytest

from orket.runtime.evidence_package_generator_contract import (
    evidence_package_generator_contract_snapshot,
    validate_evidence_package_generator_contract,
)


# Layer: unit
def test_evidence_package_generator_contract_snapshot_contains_expected_sections() -> None:
    payload = evidence_package_generator_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    required_sections = set(payload["required_sections"])
    assert required_sections == {
        "gate_summary",
        "drift_report",
        "release_confidence_scorecard",
        "non_fatal_error_budget",
        "interface_freeze_windows",
        "promotion_rollback_criteria",
        "artifact_inventory",
        "decision_record",
    }


# Layer: contract
def test_validate_evidence_package_generator_contract_accepts_current_snapshot() -> None:
    required_sections = validate_evidence_package_generator_contract()
    assert "gate_summary" in required_sections


# Layer: contract
def test_validate_evidence_package_generator_contract_rejects_required_sections_mismatch() -> None:
    payload = evidence_package_generator_contract_snapshot()
    payload["required_sections"] = [row for row in payload["required_sections"] if row != "drift_report"]
    with pytest.raises(ValueError, match="E_EVIDENCE_PACKAGE_GENERATOR_CONTRACT_REQUIRED_SECTIONS_MISMATCH"):
        _ = validate_evidence_package_generator_contract(payload)
