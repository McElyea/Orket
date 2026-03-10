from __future__ import annotations

import pytest

from orket.runtime.decision_record_operating_principles_contract import (
    decision_record_operating_principles_contract_snapshot,
    validate_decision_record_operating_principles_contract,
)


# Layer: unit
def test_decision_record_operating_principles_contract_snapshot_contains_expected_check_ids() -> None:
    payload = decision_record_operating_principles_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    check_ids = {row["check_id"] for row in payload["checks"]}
    assert check_ids == {
        "decision_log_template_sections_present",
        "operating_principles_sections_present",
    }


# Layer: contract
def test_validate_decision_record_operating_principles_contract_accepts_current_snapshot() -> None:
    check_ids = validate_decision_record_operating_principles_contract()
    assert "decision_log_template_sections_present" in check_ids


# Layer: contract
def test_validate_decision_record_operating_principles_contract_rejects_check_set_mismatch() -> None:
    payload = decision_record_operating_principles_contract_snapshot()
    payload["checks"] = [row for row in payload["checks"] if row["check_id"] != "operating_principles_sections_present"]
    with pytest.raises(ValueError, match="E_DECISION_RECORD_OPERATING_PRINCIPLES_CONTRACT_CHECK_ID_SET_MISMATCH"):
        _ = validate_decision_record_operating_principles_contract(payload)
