from __future__ import annotations

from typing import Any


PERSISTENCE_CORRUPTION_TEST_CONTRACT_SCHEMA_VERSION = "1.0"

_EXPECTED_CHECK_IDS = {
    "checksum_corruption_rejected",
    "non_monotonic_sequence_rejected",
    "partial_tail_replayed_safely",
}
_ALLOWED_OUTCOMES = {
    "raise_error",
    "safe_recovery",
}
_ALLOWED_ERROR_CODES = {
    "",
    "E_LEDGER_CORRUPT",
    "E_LEDGER_SEQ",
}


def persistence_corruption_test_contract_snapshot() -> dict[str, Any]:
    return {
        "schema_version": PERSISTENCE_CORRUPTION_TEST_CONTRACT_SCHEMA_VERSION,
        "target_surface": "orket.adapters.storage.protocol_append_only_ledger.AppendOnlyRunLedger",
        "checks": [
            {
                "check_id": "checksum_corruption_rejected",
                "corruption_mode": "checksum_bit_flip",
                "expected_outcome": "raise_error",
                "expected_error_code": "E_LEDGER_CORRUPT",
            },
            {
                "check_id": "non_monotonic_sequence_rejected",
                "corruption_mode": "event_seq_regression",
                "expected_outcome": "raise_error",
                "expected_error_code": "E_LEDGER_SEQ",
            },
            {
                "check_id": "partial_tail_replayed_safely",
                "corruption_mode": "truncated_last_frame",
                "expected_outcome": "safe_recovery",
                "expected_error_code": "",
            },
        ],
    }


def validate_persistence_corruption_test_contract(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    contract = dict(payload or persistence_corruption_test_contract_snapshot())
    target_surface = str(contract.get("target_surface") or "").strip()
    if not target_surface:
        raise ValueError("E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_SURFACE_REQUIRED")

    checks = list(contract.get("checks") or [])
    if not checks:
        raise ValueError("E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_EMPTY")

    observed_check_ids: list[str] = []
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError("E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_ROW_SCHEMA")
        check_id = str(row.get("check_id") or "").strip()
        corruption_mode = str(row.get("corruption_mode") or "").strip()
        expected_outcome = str(row.get("expected_outcome") or "").strip()
        expected_error_code = str(row.get("expected_error_code") or "").strip()
        if not check_id:
            raise ValueError("E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_CHECK_ID_REQUIRED")
        if not corruption_mode:
            raise ValueError(f"E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_MODE_REQUIRED:{check_id}")
        if expected_outcome not in _ALLOWED_OUTCOMES:
            raise ValueError(f"E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_OUTCOME_INVALID:{check_id}")
        if expected_error_code not in _ALLOWED_ERROR_CODES:
            raise ValueError(f"E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_ERROR_CODE_INVALID:{check_id}")
        if expected_outcome == "raise_error" and not expected_error_code:
            raise ValueError(f"E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_ERROR_CODE_REQUIRED:{check_id}")
        if expected_outcome == "safe_recovery" and expected_error_code:
            raise ValueError(f"E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_ERROR_CODE_FORBIDDEN:{check_id}")
        observed_check_ids.append(check_id)

    if len(set(observed_check_ids)) != len(observed_check_ids):
        raise ValueError("E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_DUPLICATE_CHECK_ID")
    if set(observed_check_ids) != _EXPECTED_CHECK_IDS:
        raise ValueError("E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_CHECK_ID_SET_MISMATCH")
    return tuple(sorted(observed_check_ids))
