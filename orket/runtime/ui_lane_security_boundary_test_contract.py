from __future__ import annotations

from typing import Any


UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_SCHEMA_VERSION = "1.0"

_EXPECTED_CHECK_IDS = {
    "explorer_path_traversal_blocked",
    "session_workspace_escape_blocked",
    "companion_error_mapping_is_structured",
    "ui_state_registry_blocked_boundary_enforced",
}


def ui_lane_security_boundary_test_contract_snapshot() -> dict[str, Any]:
    return {
        "schema_version": UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_SCHEMA_VERSION,
        "checks": [
            {
                "check_id": "explorer_path_traversal_blocked",
                "surface": "orket.decision_nodes.api_runtime_strategy_node.DefaultApiRuntimeStrategyNode.resolve_explorer_path",
                "expected_behavior": "path traversal requests are rejected with None target",
            },
            {
                "check_id": "session_workspace_escape_blocked",
                "surface": "orket.interfaces.api._validate_session_path",
                "expected_behavior": "session_id path escape raises HTTP 400",
            },
            {
                "check_id": "companion_error_mapping_is_structured",
                "surface": "orket.interfaces.routers.companion._raise_companion_http_error",
                "expected_behavior": "ValueError maps to HTTP 400 detail with code/message structure",
            },
            {
                "check_id": "ui_state_registry_blocked_boundary_enforced",
                "surface": "orket.runtime.state_transition_registry.state_transition_registry_snapshot",
                "expected_behavior": "ui blocked state transitions only to ready/degraded",
            },
        ],
    }


def validate_ui_lane_security_boundary_test_contract(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    contract = dict(payload or ui_lane_security_boundary_test_contract_snapshot())
    checks = list(contract.get("checks") or [])
    if not checks:
        raise ValueError("E_UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_EMPTY")

    observed_check_ids: list[str] = []
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError("E_UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_ROW_SCHEMA")
        check_id = str(row.get("check_id") or "").strip()
        surface = str(row.get("surface") or "").strip()
        expected_behavior = str(row.get("expected_behavior") or "").strip()
        if not check_id:
            raise ValueError("E_UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_CHECK_ID_REQUIRED")
        if not surface:
            raise ValueError(f"E_UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_SURFACE_REQUIRED:{check_id}")
        if not expected_behavior:
            raise ValueError(f"E_UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_EXPECTED_BEHAVIOR_REQUIRED:{check_id}")
        observed_check_ids.append(check_id)

    if len(set(observed_check_ids)) != len(observed_check_ids):
        raise ValueError("E_UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_DUPLICATE_CHECK_ID")
    if set(observed_check_ids) != _EXPECTED_CHECK_IDS:
        raise ValueError("E_UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_CHECK_ID_SET_MISMATCH")
    return tuple(sorted(observed_check_ids))
