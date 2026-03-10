from __future__ import annotations

import pytest

from orket.runtime.long_session_soak_test_contract import (
    long_session_soak_test_contract_snapshot,
    validate_long_session_soak_test_contract,
)


# Layer: unit
def test_long_session_soak_test_contract_snapshot_contains_expected_check_ids() -> None:
    payload = long_session_soak_test_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    assert int(payload["turn_count"]) >= 100
    check_ids = {row["check_id"] for row in payload["checks"]}
    assert check_ids == {
        "stub_provider_no_error_events_across_soak_turns",
        "stub_provider_terminal_event_per_turn",
        "stub_provider_event_order_stable_across_soak_turns",
    }


# Layer: contract
def test_validate_long_session_soak_test_contract_accepts_current_snapshot() -> None:
    check_ids = validate_long_session_soak_test_contract()
    assert "stub_provider_terminal_event_per_turn" in check_ids


# Layer: contract
def test_validate_long_session_soak_test_contract_rejects_turn_count_too_small() -> None:
    payload = long_session_soak_test_contract_snapshot()
    payload["turn_count"] = 10
    with pytest.raises(ValueError, match="E_LONG_SESSION_SOAK_TEST_CONTRACT_TURN_COUNT_TOO_SMALL"):
        _ = validate_long_session_soak_test_contract(payload)


# Layer: contract
def test_validate_long_session_soak_test_contract_rejects_check_set_mismatch() -> None:
    payload = long_session_soak_test_contract_snapshot()
    payload["checks"] = [row for row in payload["checks"] if row["check_id"] != "stub_provider_terminal_event_per_turn"]
    with pytest.raises(ValueError, match="E_LONG_SESSION_SOAK_TEST_CONTRACT_CHECK_ID_SET_MISMATCH"):
        _ = validate_long_session_soak_test_contract(payload)
