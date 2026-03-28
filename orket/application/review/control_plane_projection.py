from __future__ import annotations

from typing import Any


REVIEW_EXECUTION_STATE_AUTHORITY = "control_plane_records"
REVIEW_CONTROL_PLANE_PROJECTION_SOURCE = REVIEW_EXECUTION_STATE_AUTHORITY


def validate_review_execution_authority_markers(
    *,
    execution_state_authority: Any,
    execution_state_authoritative: Any,
    field_name: str,
) -> None:
    if str(execution_state_authority or "").strip() != REVIEW_EXECUTION_STATE_AUTHORITY:
        raise ValueError(f"{field_name}_execution_state_authority_invalid")
    if execution_state_authoritative is not False:
        raise ValueError(f"{field_name}_execution_state_authoritative_invalid")


def validate_review_execution_state_payload(
    payload: Any,
    *,
    field_name: str,
    authoritative_flag_field: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{field_name}_invalid")
    validate_review_execution_authority_markers(
        execution_state_authority=payload.get("execution_state_authority"),
        execution_state_authoritative=payload.get(authoritative_flag_field),
        field_name=field_name,
    )
    return dict(payload)


def validate_review_control_plane_summary(summary: Any) -> dict[str, Any]:
    if not isinstance(summary, dict):
        raise ValueError("review_control_plane_summary_invalid")
    if str(summary.get("projection_source") or "").strip() != REVIEW_CONTROL_PLANE_PROJECTION_SOURCE:
        raise ValueError("review_control_plane_projection_source_invalid")
    if summary.get("projection_only") is not True:
        raise ValueError("review_control_plane_projection_only_invalid")
    return dict(summary)


__all__ = [
    "REVIEW_EXECUTION_STATE_AUTHORITY",
    "REVIEW_CONTROL_PLANE_PROJECTION_SOURCE",
    "validate_review_execution_authority_markers",
    "validate_review_execution_state_payload",
    "validate_review_control_plane_summary",
]
