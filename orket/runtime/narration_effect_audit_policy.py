from __future__ import annotations

from typing import Any


NARRATION_EFFECT_AUDIT_POLICY_SCHEMA_VERSION = "1.0"

_EXPECTED_TOOLS = {
    "update_issue_status",
    "write_file",
}
_EXPECTED_FAILURE_REASONS = {
    "artifact_path_missing",
    "artifact_path_outside_workspace",
    "card_status_target_missing",
    "card_status_transition_missing",
    "workspace_artifact_missing",
}
_EXPECTED_AUDIT_STATUSES = {
    "missing",
    "verified",
}
_POLICY_ROWS: tuple[dict[str, Any], ...] = (
    {
        "tool": "write_file",
        "verification": "workspace_artifact_exists",
        "failure_reasons": [
            "artifact_path_missing",
            "artifact_path_outside_workspace",
            "workspace_artifact_missing",
        ],
    },
    {
        "tool": "update_issue_status",
        "verification": "card_history_transition_present",
        "failure_reasons": [
            "card_status_target_missing",
            "card_status_transition_missing",
        ],
    },
)


def narration_effect_audit_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": NARRATION_EFFECT_AUDIT_POLICY_SCHEMA_VERSION,
        "audit_statuses": sorted(_EXPECTED_AUDIT_STATUSES),
        "failure_reasons": sorted(_EXPECTED_FAILURE_REASONS),
        "rows": [dict(row) for row in _POLICY_ROWS],
    }


def validate_narration_effect_audit_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or narration_effect_audit_policy_snapshot())
    rows = list(policy.get("rows") or [])
    if not rows:
        raise ValueError("E_NARRATION_EFFECT_AUDIT_POLICY_EMPTY")

    observed_tools: list[str] = []
    observed_failure_reasons: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_NARRATION_EFFECT_AUDIT_POLICY_ROW_SCHEMA")
        tool = str(row.get("tool") or "").strip().lower()
        verification = str(row.get("verification") or "").strip().lower()
        failure_reasons = {str(token).strip().lower() for token in row.get("failure_reasons", []) if str(token).strip()}
        if not tool:
            raise ValueError("E_NARRATION_EFFECT_AUDIT_POLICY_TOOL_REQUIRED")
        if not verification:
            raise ValueError(f"E_NARRATION_EFFECT_AUDIT_POLICY_VERIFICATION_REQUIRED:{tool}")
        if not failure_reasons:
            raise ValueError(f"E_NARRATION_EFFECT_AUDIT_POLICY_FAILURE_REASONS_REQUIRED:{tool}")
        observed_tools.append(tool)
        observed_failure_reasons.update(failure_reasons)

    if len(set(observed_tools)) != len(observed_tools):
        raise ValueError("E_NARRATION_EFFECT_AUDIT_POLICY_DUPLICATE_TOOL")
    if set(observed_tools) != _EXPECTED_TOOLS:
        raise ValueError("E_NARRATION_EFFECT_AUDIT_POLICY_TOOL_SET_MISMATCH")

    audit_statuses = {str(token).strip().lower() for token in policy.get("audit_statuses", []) if str(token).strip()}
    if audit_statuses != _EXPECTED_AUDIT_STATUSES:
        raise ValueError("E_NARRATION_EFFECT_AUDIT_POLICY_AUDIT_STATUS_SET_MISMATCH")

    failure_reasons = {str(token).strip().lower() for token in policy.get("failure_reasons", []) if str(token).strip()}
    if failure_reasons != _EXPECTED_FAILURE_REASONS or observed_failure_reasons != _EXPECTED_FAILURE_REASONS:
        raise ValueError("E_NARRATION_EFFECT_AUDIT_POLICY_FAILURE_REASON_SET_MISMATCH")

    return tuple(sorted(observed_tools))
