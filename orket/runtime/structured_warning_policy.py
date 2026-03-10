from __future__ import annotations

from typing import Any


_WARNING_ROWS: tuple[dict[str, Any], ...] = (
    {
        "warning_code": "W_RUNTIME_TRUTH_DRIFT_DETECTED",
        "severity": "high",
        "emission_surface": "runtime_truth_contract_drift_report",
        "required_fields": ["check", "observed", "expected"],
    },
    {
        "warning_code": "W_PROVIDER_QUARANTINED",
        "severity": "medium",
        "emission_surface": "provider_runtime_target",
        "required_fields": ["requested_provider", "canonical_provider", "resolution_mode"],
    },
    {
        "warning_code": "W_RUNTIME_DEGRADED",
        "severity": "medium",
        "emission_surface": "runtime_status_vocabulary",
        "required_fields": ["status", "reason_code"],
    },
    {
        "warning_code": "W_ENV_PARITY_MISMATCH",
        "severity": "low",
        "emission_surface": "check_environment_parity_checklist",
        "required_fields": ["check", "expected", "observed"],
    },
)
_SEVERITY_ORDER = {"low", "medium", "high", "critical"}


def structured_warning_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "warnings": [dict(row) for row in _WARNING_ROWS],
    }


def validate_structured_warning_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or structured_warning_policy_snapshot())
    rows = list(policy.get("warnings") or [])
    if not rows:
        raise ValueError("E_WARNING_POLICY_EMPTY")
    warning_codes: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_WARNING_POLICY_ROW_SCHEMA")
        warning_code = str(row.get("warning_code") or "").strip()
        severity = str(row.get("severity") or "").strip().lower()
        emission_surface = str(row.get("emission_surface") or "").strip()
        required_fields = [str(token).strip() for token in row.get("required_fields", []) if str(token).strip()]
        if not warning_code or not emission_surface:
            raise ValueError("E_WARNING_POLICY_ROW_SCHEMA")
        if severity not in _SEVERITY_ORDER:
            raise ValueError(f"E_WARNING_POLICY_SEVERITY_INVALID:{warning_code}")
        if not required_fields:
            raise ValueError(f"E_WARNING_POLICY_REQUIRED_FIELDS_EMPTY:{warning_code}")
        warning_codes.append(warning_code)
    if len(set(warning_codes)) != len(warning_codes):
        raise ValueError("E_WARNING_POLICY_DUPLICATE_CODE")
    return tuple(sorted(warning_codes))
