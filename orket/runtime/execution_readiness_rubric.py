from __future__ import annotations

from typing import Any


EXECUTION_READINESS_RUBRIC_SCHEMA_VERSION = "1.0"

_EXPECTED_CRITERIA = {
    "contract_drift_clean",
    "acceptance_gate_green",
    "runtime_boundary_audit_passed",
    "docs_hygiene_passed",
}
_ALLOWED_SEVERITIES = {"blocker", "advisory"}


def execution_readiness_rubric_snapshot() -> dict[str, Any]:
    return {
        "schema_version": EXECUTION_READINESS_RUBRIC_SCHEMA_VERSION,
        "minimum_score": 0.9,
        "criteria": [
            {
                "criterion": "contract_drift_clean",
                "weight": 0.3,
                "severity": "blocker",
            },
            {
                "criterion": "acceptance_gate_green",
                "weight": 0.3,
                "severity": "blocker",
            },
            {
                "criterion": "runtime_boundary_audit_passed",
                "weight": 0.2,
                "severity": "blocker",
            },
            {
                "criterion": "docs_hygiene_passed",
                "weight": 0.2,
                "severity": "advisory",
            },
        ],
    }


def validate_execution_readiness_rubric(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    rubric = dict(payload or execution_readiness_rubric_snapshot())

    minimum_score = rubric.get("minimum_score")
    if not isinstance(minimum_score, (float, int)):
        raise ValueError("E_EXECUTION_READINESS_RUBRIC_MIN_SCORE_SCHEMA")
    min_score_float = float(minimum_score)
    if not (0.0 <= min_score_float <= 1.0):
        raise ValueError("E_EXECUTION_READINESS_RUBRIC_MIN_SCORE_RANGE")

    rows = list(rubric.get("criteria") or [])
    if not rows:
        raise ValueError("E_EXECUTION_READINESS_RUBRIC_CRITERIA_EMPTY")

    observed_criteria: list[str] = []
    weight_total = 0.0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_EXECUTION_READINESS_RUBRIC_ROW_SCHEMA")
        criterion = str(row.get("criterion") or "").strip()
        if not criterion:
            raise ValueError("E_EXECUTION_READINESS_RUBRIC_CRITERION_REQUIRED")

        weight = row.get("weight")
        if not isinstance(weight, (float, int)):
            raise ValueError(f"E_EXECUTION_READINESS_RUBRIC_WEIGHT_SCHEMA:{criterion}")
        weight_float = float(weight)
        if not (0.0 < weight_float <= 1.0):
            raise ValueError(f"E_EXECUTION_READINESS_RUBRIC_WEIGHT_RANGE:{criterion}")

        severity = str(row.get("severity") or "").strip().lower()
        if severity not in _ALLOWED_SEVERITIES:
            raise ValueError(f"E_EXECUTION_READINESS_RUBRIC_SEVERITY_INVALID:{criterion}")

        observed_criteria.append(criterion)
        weight_total += weight_float

    if len(set(observed_criteria)) != len(observed_criteria):
        raise ValueError("E_EXECUTION_READINESS_RUBRIC_DUPLICATE_CRITERION")
    if {token for token in observed_criteria} != _EXPECTED_CRITERIA:
        raise ValueError("E_EXECUTION_READINESS_RUBRIC_CRITERIA_SET_MISMATCH")
    if abs(weight_total - 1.0) > 1e-9:
        raise ValueError("E_EXECUTION_READINESS_RUBRIC_WEIGHT_TOTAL_INVALID")

    return tuple(sorted(observed_criteria))
