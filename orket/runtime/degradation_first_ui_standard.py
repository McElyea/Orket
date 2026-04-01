from __future__ import annotations

from typing import Any


DEGRADATION_FIRST_UI_STANDARD_SCHEMA_VERSION = "1.0"

_EXPECTED_CHECK_IDS = {
    "runtime_status_vocabulary_includes_degraded",
    "ui_state_registry_includes_degraded_state",
    "structured_warning_policy_declares_runtime_degraded",
    "companion_models_unavailable_returns_truthful_degraded_failure",
}


def degradation_first_ui_standard_snapshot() -> dict[str, Any]:
    return {
        "schema_version": DEGRADATION_FIRST_UI_STANDARD_SCHEMA_VERSION,
        "checks": [
            {
                "check_id": "runtime_status_vocabulary_includes_degraded",
                "surface": "orket.runtime.runtime_truth_contracts.runtime_status_vocabulary_snapshot",
                "expected_behavior": "runtime status vocabulary includes degraded state token",
            },
            {
                "check_id": "ui_state_registry_includes_degraded_state",
                "surface": "orket.runtime.state_transition_registry.state_transition_registry_snapshot",
                "expected_behavior": "ui domain states include degraded",
            },
            {
                "check_id": "structured_warning_policy_declares_runtime_degraded",
                "surface": "orket.runtime.structured_warning_policy.structured_warning_policy_snapshot",
                "expected_behavior": "warning policy includes W_RUNTIME_DEGRADED code",
            },
            {
                "check_id": "companion_models_unavailable_returns_truthful_degraded_failure",
                "surface": "orket.interfaces.routers.extension_runtime.build_extension_runtime_router",
                "expected_behavior": "companion models failures return ok=false, degraded=true, and an unavailable error",
            },
        ],
    }


def validate_degradation_first_ui_standard(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    standard = dict(payload or degradation_first_ui_standard_snapshot())
    checks = list(standard.get("checks") or [])
    if not checks:
        raise ValueError("E_DEGRADATION_FIRST_UI_STANDARD_EMPTY")

    observed_check_ids: list[str] = []
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError("E_DEGRADATION_FIRST_UI_STANDARD_ROW_SCHEMA")
        check_id = str(row.get("check_id") or "").strip()
        surface = str(row.get("surface") or "").strip()
        expected_behavior = str(row.get("expected_behavior") or "").strip()
        if not check_id:
            raise ValueError("E_DEGRADATION_FIRST_UI_STANDARD_CHECK_ID_REQUIRED")
        if not surface:
            raise ValueError(f"E_DEGRADATION_FIRST_UI_STANDARD_SURFACE_REQUIRED:{check_id}")
        if not expected_behavior:
            raise ValueError(f"E_DEGRADATION_FIRST_UI_STANDARD_EXPECTED_BEHAVIOR_REQUIRED:{check_id}")
        observed_check_ids.append(check_id)

    if len(set(observed_check_ids)) != len(observed_check_ids):
        raise ValueError("E_DEGRADATION_FIRST_UI_STANDARD_DUPLICATE_CHECK_ID")
    if set(observed_check_ids) != _EXPECTED_CHECK_IDS:
        raise ValueError("E_DEGRADATION_FIRST_UI_STANDARD_CHECK_ID_SET_MISMATCH")
    return tuple(sorted(observed_check_ids))
