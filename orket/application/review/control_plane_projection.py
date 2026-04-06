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


def validate_review_control_plane_ref_hierarchy(
    *,
    control_plane_run_id: str,
    control_plane_attempt_id: str,
    control_plane_step_id: str,
    run_id_error: str,
    attempt_id_error: str,
) -> None:
    if (control_plane_attempt_id or control_plane_step_id) and not control_plane_run_id:
        raise ValueError(run_id_error)
    if control_plane_step_id and not control_plane_attempt_id:
        raise ValueError(attempt_id_error)


def validate_review_control_plane_ref_run_lineage(
    *,
    control_plane_run_id: str,
    control_plane_attempt_id: str,
    control_plane_step_id: str,
    attempt_id_error: str,
    step_id_error: str,
) -> None:
    normalized_run_id = str(control_plane_run_id or "").strip()
    normalized_attempt_id = str(control_plane_attempt_id or "").strip()
    normalized_step_id = str(control_plane_step_id or "").strip()
    if normalized_attempt_id and not normalized_attempt_id.startswith(f"{normalized_run_id}:attempt:"):
        raise ValueError(attempt_id_error)
    if normalized_step_id and not normalized_step_id.startswith(f"{normalized_run_id}:step:"):
        raise ValueError(step_id_error)


def validate_review_required_identifier(value: Any, *, error: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(error)
    return normalized


def validate_review_matching_identifier(
    value: Any,
    *,
    expected: str,
    error: str,
) -> str:
    normalized = str(value or "").strip()
    if normalized and normalized != str(expected or "").strip():
        raise ValueError(error)
    return normalized


def validate_review_control_plane_summary(
    summary: Any,
    *,
    expected_run_id: str = "",
    expected_attempt_id: str = "",
    expected_step_id: str = "",
) -> dict[str, Any]:
    if not isinstance(summary, dict):
        raise ValueError("review_control_plane_summary_invalid")
    if str(summary.get("projection_source") or "").strip() != REVIEW_CONTROL_PLANE_PROJECTION_SOURCE:
        raise ValueError("review_control_plane_projection_source_invalid")
    if summary.get("projection_only") is not True:
        raise ValueError("review_control_plane_projection_only_invalid")

    normalized_summary = dict(summary)
    projected_run_id = str(normalized_summary.get("run_id") or "").strip()
    projected_attempt_id = str(normalized_summary.get("attempt_id") or "").strip()
    projected_step_id = str(normalized_summary.get("step_id") or "").strip()
    projected_attempt_state = str(normalized_summary.get("attempt_state") or "").strip()
    projected_step_kind = str(normalized_summary.get("step_kind") or "").strip()
    projected_attempt_ordinal = normalized_summary.get("attempt_ordinal")

    validate_review_control_plane_ref_hierarchy(
        control_plane_run_id=projected_run_id,
        control_plane_attempt_id=projected_attempt_id,
        control_plane_step_id=projected_step_id,
        run_id_error="review_control_plane_run_id_required",
        attempt_id_error="review_control_plane_attempt_id_required",
    )
    if (projected_attempt_state or projected_attempt_ordinal not in (None, "")) and not projected_attempt_id:
        raise ValueError("review_control_plane_attempt_id_required")
    if projected_step_kind and not projected_step_id:
        raise ValueError("review_control_plane_step_id_required")
    if projected_run_id:
        validate_review_control_plane_ref_run_lineage(
            control_plane_run_id=projected_run_id,
            control_plane_attempt_id=projected_attempt_id,
            control_plane_step_id=projected_step_id,
            attempt_id_error="review_control_plane_attempt_id_run_lineage_mismatch",
            step_id_error="review_control_plane_step_id_run_lineage_mismatch",
        )

    if projected_run_id:
        for field_name in (
            "run_state",
            "workload_id",
            "workload_version",
            "policy_snapshot_id",
            "configuration_snapshot_id",
        ):
            if not str(normalized_summary.get(field_name) or "").strip():
                raise ValueError(f"review_control_plane_{field_name}_required")
    if projected_attempt_id and not projected_attempt_state:
        raise ValueError("review_control_plane_attempt_state_required")
    if projected_attempt_id:
        try:
            attempt_ordinal = (
                projected_attempt_ordinal
                if isinstance(projected_attempt_ordinal, int)
                else int(str(projected_attempt_ordinal or "").strip())
            )
        except (TypeError, ValueError):
            raise ValueError("review_control_plane_attempt_ordinal_required") from None
        if attempt_ordinal <= 0:
            raise ValueError("review_control_plane_attempt_ordinal_required")
    if projected_step_id and not projected_step_kind:
        raise ValueError("review_control_plane_step_kind_required")

    if str(expected_run_id or "").strip() and projected_run_id != str(expected_run_id).strip():
        raise ValueError("review_control_plane_run_id_mismatch")
    if str(expected_attempt_id or "").strip() and projected_attempt_id != str(expected_attempt_id).strip():
        raise ValueError("review_control_plane_attempt_id_mismatch")
    if str(expected_step_id or "").strip() and projected_step_id != str(expected_step_id).strip():
        raise ValueError("review_control_plane_step_id_mismatch")
    return normalized_summary


__all__ = [
    "REVIEW_EXECUTION_STATE_AUTHORITY",
    "REVIEW_CONTROL_PLANE_PROJECTION_SOURCE",
    "validate_review_control_plane_ref_hierarchy",
    "validate_review_control_plane_ref_run_lineage",
    "validate_review_matching_identifier",
    "validate_review_required_identifier",
    "validate_review_execution_authority_markers",
    "validate_review_execution_state_payload",
    "validate_review_control_plane_summary",
]
