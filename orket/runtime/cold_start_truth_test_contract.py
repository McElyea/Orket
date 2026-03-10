from __future__ import annotations

from typing import Any


COLD_START_TRUTH_TEST_CONTRACT_SCHEMA_VERSION = "1.0"

_EXPECTED_CHECK_IDS = {
    "stub_cold_start_true_loading_payload",
    "stub_cold_start_false_loading_payload",
    "stub_loading_precedes_ready_event",
}


def cold_start_truth_test_contract_snapshot() -> dict[str, Any]:
    return {
        "schema_version": COLD_START_TRUTH_TEST_CONTRACT_SCHEMA_VERSION,
        "checks": [
            {
                "check_id": "stub_cold_start_true_loading_payload",
                "surface": "orket.streaming.model_provider.StubModelStreamProvider",
                "expected_behavior": "force_cold_model_load=true emits loading payload cold_start=true progress=0.0",
            },
            {
                "check_id": "stub_cold_start_false_loading_payload",
                "surface": "orket.streaming.model_provider.StubModelStreamProvider",
                "expected_behavior": "force_cold_model_load=false emits loading payload cold_start=false progress=1.0",
            },
            {
                "check_id": "stub_loading_precedes_ready_event",
                "surface": "orket.streaming.model_provider.StubModelStreamProvider",
                "expected_behavior": "selected -> loading -> ready event order is preserved",
            },
        ],
    }


def validate_cold_start_truth_test_contract(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    contract = dict(payload or cold_start_truth_test_contract_snapshot())
    checks = list(contract.get("checks") or [])
    if not checks:
        raise ValueError("E_COLD_START_TRUTH_TEST_CONTRACT_EMPTY")

    observed_check_ids: list[str] = []
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError("E_COLD_START_TRUTH_TEST_CONTRACT_ROW_SCHEMA")
        check_id = str(row.get("check_id") or "").strip()
        surface = str(row.get("surface") or "").strip()
        expected_behavior = str(row.get("expected_behavior") or "").strip()
        if not check_id:
            raise ValueError("E_COLD_START_TRUTH_TEST_CONTRACT_CHECK_ID_REQUIRED")
        if not surface:
            raise ValueError(f"E_COLD_START_TRUTH_TEST_CONTRACT_SURFACE_REQUIRED:{check_id}")
        if not expected_behavior:
            raise ValueError(f"E_COLD_START_TRUTH_TEST_CONTRACT_EXPECTED_BEHAVIOR_REQUIRED:{check_id}")
        observed_check_ids.append(check_id)

    if len(set(observed_check_ids)) != len(observed_check_ids):
        raise ValueError("E_COLD_START_TRUTH_TEST_CONTRACT_DUPLICATE_CHECK_ID")
    if set(observed_check_ids) != _EXPECTED_CHECK_IDS:
        raise ValueError("E_COLD_START_TRUTH_TEST_CONTRACT_CHECK_ID_SET_MISMATCH")
    return tuple(sorted(observed_check_ids))
