from __future__ import annotations

from typing import Any

HUMAN_CORRECTION_CAPTURE_POLICY_SCHEMA_VERSION = "1.0"

_REQUIRED_FIELDS = {
    "run_id",
    "correction_id",
    "submitted_by",
    "target_surface",
    "before_value",
    "after_value",
    "reason",
    "timestamp",
}
_TARGET_SURFACES = {
    "route_decision",
    "prompt_render",
    "tool_result",
    "final_response",
}


def human_correction_capture_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": HUMAN_CORRECTION_CAPTURE_POLICY_SCHEMA_VERSION,
        "required_fields": sorted(_REQUIRED_FIELDS),
        "target_surfaces": sorted(_TARGET_SURFACES),
        "persistence": {
            "store": "run_ledger",
            "emit_warning_event": True,
            "retain_original_value": True,
        },
    }


def validate_human_correction_capture_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or human_correction_capture_policy_snapshot())

    required_fields = [str(token or "").strip() for token in policy.get("required_fields", [])]
    if not required_fields or any(not token for token in required_fields):
        raise ValueError("E_HUMAN_CORRECTION_CAPTURE_REQUIRED_FIELDS_EMPTY")
    if {field for field in required_fields if field} != _REQUIRED_FIELDS:
        raise ValueError("E_HUMAN_CORRECTION_CAPTURE_REQUIRED_FIELDS_MISMATCH")

    target_surfaces = [str(token or "").strip() for token in policy.get("target_surfaces", [])]
    if not target_surfaces or any(not token for token in target_surfaces):
        raise ValueError("E_HUMAN_CORRECTION_CAPTURE_TARGET_SURFACES_EMPTY")
    if {surface for surface in target_surfaces if surface} != _TARGET_SURFACES:
        raise ValueError("E_HUMAN_CORRECTION_CAPTURE_TARGET_SURFACES_MISMATCH")

    persistence = policy.get("persistence")
    if not isinstance(persistence, dict):
        raise ValueError("E_HUMAN_CORRECTION_CAPTURE_PERSISTENCE_SCHEMA")
    if str(persistence.get("store") or "").strip() != "run_ledger":
        raise ValueError("E_HUMAN_CORRECTION_CAPTURE_STORE_INVALID")
    if not isinstance(persistence.get("emit_warning_event"), bool):
        raise ValueError("E_HUMAN_CORRECTION_CAPTURE_EMIT_WARNING_INVALID")
    if not isinstance(persistence.get("retain_original_value"), bool):
        raise ValueError("E_HUMAN_CORRECTION_CAPTURE_RETAIN_ORIGINAL_INVALID")

    return tuple(sorted(_TARGET_SURFACES))
