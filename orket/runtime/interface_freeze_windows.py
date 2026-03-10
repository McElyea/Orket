from __future__ import annotations

from typing import Any


INTERFACE_FREEZE_WINDOWS_SCHEMA_VERSION = "1.0"

_EXPECTED_WINDOW_IDS = {
    "pre_promotion_contract_freeze",
    "promotion_candidate_interface_freeze",
    "post_promotion_observation_freeze",
}
_ALLOWED_OVERRIDE_POLICIES = {
    "operator_override_required",
    "emergency_break_glass",
}
_EXPECTED_OVERRIDE_FIELDS = {
    "override_type",
    "operator",
    "justification",
    "approval_ticket",
}


def interface_freeze_windows_snapshot() -> dict[str, Any]:
    return {
        "schema_version": INTERFACE_FREEZE_WINDOWS_SCHEMA_VERSION,
        "windows": [
            {
                "window_id": "pre_promotion_contract_freeze",
                "scope": "runtime_contracts",
                "duration_hours": 24,
                "blocked_change_classes": [
                    "schema_breaking_change",
                    "required_field_removal",
                    "contract_error_code_removal",
                ],
                "override_policy": "operator_override_required",
            },
            {
                "window_id": "promotion_candidate_interface_freeze",
                "scope": "runtime_interfaces",
                "duration_hours": 12,
                "blocked_change_classes": [
                    "api_shape_change",
                    "cli_flag_removal",
                    "policy_semantics_change",
                ],
                "override_policy": "operator_override_required",
            },
            {
                "window_id": "post_promotion_observation_freeze",
                "scope": "runtime_execution",
                "duration_hours": 12,
                "blocked_change_classes": [
                    "fallback_path_change",
                    "repair_semantics_change",
                    "telemetry_schema_change",
                ],
                "override_policy": "emergency_break_glass",
            },
        ],
        "emergency_break_policy": {
            "override_log_required": True,
            "required_override_fields": [
                "override_type",
                "operator",
                "justification",
                "approval_ticket",
            ],
            "max_break_glass_duration_hours": 4,
        },
    }


def validate_interface_freeze_windows(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    freeze_windows = dict(payload or interface_freeze_windows_snapshot())
    _validate_emergency_break_policy(freeze_windows.get("emergency_break_policy"))

    windows = list(freeze_windows.get("windows") or [])
    if not windows:
        raise ValueError("E_INTERFACE_FREEZE_WINDOWS_EMPTY")

    observed_window_ids: list[str] = []
    for row in windows:
        if not isinstance(row, dict):
            raise ValueError("E_INTERFACE_FREEZE_WINDOWS_ROW_SCHEMA")
        window_id = str(row.get("window_id") or "").strip()
        scope = str(row.get("scope") or "").strip()
        duration_hours = _coerce_positive_int(
            row.get("duration_hours"),
            error_code="E_INTERFACE_FREEZE_WINDOWS_DURATION_INVALID",
        )
        blocked_change_classes = list(row.get("blocked_change_classes") or [])
        override_policy = str(row.get("override_policy") or "").strip()
        if not window_id:
            raise ValueError("E_INTERFACE_FREEZE_WINDOWS_ID_REQUIRED")
        if not scope:
            raise ValueError(f"E_INTERFACE_FREEZE_WINDOWS_SCOPE_REQUIRED:{window_id}")
        if duration_hours < 1:
            raise ValueError(f"E_INTERFACE_FREEZE_WINDOWS_DURATION_RANGE:{window_id}")
        if not blocked_change_classes:
            raise ValueError(f"E_INTERFACE_FREEZE_WINDOWS_BLOCKED_CHANGE_CLASSES_EMPTY:{window_id}")
        normalized_classes = [str(token).strip() for token in blocked_change_classes if str(token).strip()]
        if len(normalized_classes) != len(blocked_change_classes):
            raise ValueError(f"E_INTERFACE_FREEZE_WINDOWS_BLOCKED_CHANGE_CLASS_INVALID:{window_id}")
        if len(set(normalized_classes)) != len(normalized_classes):
            raise ValueError(f"E_INTERFACE_FREEZE_WINDOWS_BLOCKED_CHANGE_CLASS_DUPLICATE:{window_id}")
        if override_policy not in _ALLOWED_OVERRIDE_POLICIES:
            raise ValueError(f"E_INTERFACE_FREEZE_WINDOWS_OVERRIDE_POLICY_INVALID:{window_id}")
        observed_window_ids.append(window_id)

    if len(set(observed_window_ids)) != len(observed_window_ids):
        raise ValueError("E_INTERFACE_FREEZE_WINDOWS_DUPLICATE_ID")
    if set(observed_window_ids) != _EXPECTED_WINDOW_IDS:
        raise ValueError("E_INTERFACE_FREEZE_WINDOWS_ID_SET_MISMATCH")
    return tuple(sorted(observed_window_ids))


def _validate_emergency_break_policy(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("E_INTERFACE_FREEZE_WINDOWS_EMERGENCY_POLICY_SCHEMA")
    override_log_required = payload.get("override_log_required")
    required_override_fields = list(payload.get("required_override_fields") or [])
    max_break_glass_duration_hours = _coerce_positive_int(
        payload.get("max_break_glass_duration_hours"),
        error_code="E_INTERFACE_FREEZE_WINDOWS_BREAK_GLASS_DURATION_INVALID",
    )
    if override_log_required is not True:
        raise ValueError("E_INTERFACE_FREEZE_WINDOWS_OVERRIDE_LOG_REQUIRED")
    normalized_fields = {str(token).strip() for token in required_override_fields if str(token).strip()}
    if normalized_fields != _EXPECTED_OVERRIDE_FIELDS:
        raise ValueError("E_INTERFACE_FREEZE_WINDOWS_OVERRIDE_FIELDS_MISMATCH")
    if max_break_glass_duration_hours > 8:
        raise ValueError("E_INTERFACE_FREEZE_WINDOWS_BREAK_GLASS_DURATION_RANGE")


def _coerce_positive_int(value: Any, *, error_code: str) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(error_code) from exc
    if resolved < 1:
        raise ValueError(error_code)
    return resolved
