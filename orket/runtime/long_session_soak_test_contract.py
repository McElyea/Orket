from __future__ import annotations

from typing import Any

LONG_SESSION_SOAK_TEST_CONTRACT_SCHEMA_VERSION = "1.0"

_EXPECTED_CHECK_IDS = {
    "stub_provider_no_error_events_across_soak_turns",
    "stub_provider_terminal_event_per_turn",
    "stub_provider_event_order_stable_across_soak_turns",
}


def long_session_soak_test_contract_snapshot() -> dict[str, Any]:
    return {
        "schema_version": LONG_SESSION_SOAK_TEST_CONTRACT_SCHEMA_VERSION,
        "target_surface": "orket.streaming.model_provider.StubModelStreamProvider",
        "turn_count": 120,
        "checks": [
            {
                "check_id": "stub_provider_no_error_events_across_soak_turns",
                "expected_behavior": "zero error terminal events across configured soak turns",
            },
            {
                "check_id": "stub_provider_terminal_event_per_turn",
                "expected_behavior": "every turn emits exactly one stopped terminal event",
            },
            {
                "check_id": "stub_provider_event_order_stable_across_soak_turns",
                "expected_behavior": "selected -> loading -> ready -> token_delta -> stopped order per turn",
            },
        ],
    }


def validate_long_session_soak_test_contract(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    contract = dict(payload or long_session_soak_test_contract_snapshot())
    target_surface = str(contract.get("target_surface") or "").strip()
    if not target_surface:
        raise ValueError("E_LONG_SESSION_SOAK_TEST_CONTRACT_SURFACE_REQUIRED")

    turn_count = _coerce_positive_int(
        contract.get("turn_count"),
        error_code="E_LONG_SESSION_SOAK_TEST_CONTRACT_TURN_COUNT_INVALID",
    )
    if turn_count < 100:
        raise ValueError("E_LONG_SESSION_SOAK_TEST_CONTRACT_TURN_COUNT_TOO_SMALL")

    checks = list(contract.get("checks") or [])
    if not checks:
        raise ValueError("E_LONG_SESSION_SOAK_TEST_CONTRACT_EMPTY")

    observed_check_ids: list[str] = []
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError("E_LONG_SESSION_SOAK_TEST_CONTRACT_ROW_SCHEMA")
        check_id = str(row.get("check_id") or "").strip()
        expected_behavior = str(row.get("expected_behavior") or "").strip()
        if not check_id:
            raise ValueError("E_LONG_SESSION_SOAK_TEST_CONTRACT_CHECK_ID_REQUIRED")
        if not expected_behavior:
            raise ValueError(f"E_LONG_SESSION_SOAK_TEST_CONTRACT_EXPECTED_BEHAVIOR_REQUIRED:{check_id}")
        observed_check_ids.append(check_id)

    if len(set(observed_check_ids)) != len(observed_check_ids):
        raise ValueError("E_LONG_SESSION_SOAK_TEST_CONTRACT_DUPLICATE_CHECK_ID")
    if set(observed_check_ids) != _EXPECTED_CHECK_IDS:
        raise ValueError("E_LONG_SESSION_SOAK_TEST_CONTRACT_CHECK_ID_SET_MISMATCH")
    return tuple(sorted(observed_check_ids))


def _coerce_positive_int(value: Any, *, error_code: str) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(error_code) from exc
    if resolved < 1:
        raise ValueError(error_code)
    return resolved
