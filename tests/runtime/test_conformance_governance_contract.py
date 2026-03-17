from __future__ import annotations

import pytest

from orket.runtime.conformance_governance_contract import (
    conformance_governance_contract_snapshot,
    validate_conformance_governance_contract,
)


# Layer: unit
def test_conformance_governance_contract_snapshot_contains_expected_sections() -> None:
    payload = conformance_governance_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    sections = {row["section_id"] for row in payload["sections"]}
    assert sections == {
        "behavioral_contract_suite",
        "false_green_hunt_process",
        "golden_transcript_diff_policy",
        "operator_signoff_bundle",
        "repo_introspection_report",
        "cross_spec_consistency_checker",
    }


# Layer: contract
def test_validate_conformance_governance_contract_accepts_current_snapshot() -> None:
    sections = validate_conformance_governance_contract()
    assert "operator_signoff_bundle" in sections


# Layer: contract
def test_validate_conformance_governance_contract_rejects_section_set_mismatch() -> None:
    payload = conformance_governance_contract_snapshot()
    payload["sections"] = [row for row in payload["sections"] if row["section_id"] != "repo_introspection_report"]
    with pytest.raises(ValueError, match="E_CONFORMANCE_GOVERNANCE_CONTRACT_SECTION_SET_MISMATCH"):
        _ = validate_conformance_governance_contract(payload)
