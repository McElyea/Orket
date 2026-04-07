from __future__ import annotations

from typing import Any

PROMOTION_ROLLBACK_CRITERIA_SCHEMA_VERSION = "1.0"

_EXPECTED_TRIGGERS = {
    "acceptance_gate_failure",
    "contract_drift_detected",
    "critical_regression_detected",
}


def promotion_rollback_criteria_snapshot() -> dict[str, Any]:
    return {
        "schema_version": PROMOTION_ROLLBACK_CRITERIA_SCHEMA_VERSION,
        "triggers": [
            {
                "trigger": "acceptance_gate_failure",
                "action": "rollback",
                "severity": "blocker",
            },
            {
                "trigger": "contract_drift_detected",
                "action": "rollback",
                "severity": "blocker",
            },
            {
                "trigger": "critical_regression_detected",
                "action": "rollback",
                "severity": "blocker",
            },
        ],
    }


def validate_promotion_rollback_criteria(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    criteria = dict(payload or promotion_rollback_criteria_snapshot())
    rows = list(criteria.get("triggers") or [])
    if not rows:
        raise ValueError("E_PROMOTION_ROLLBACK_CRITERIA_EMPTY")

    observed_triggers: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_PROMOTION_ROLLBACK_CRITERIA_ROW_SCHEMA")
        trigger = str(row.get("trigger") or "").strip()
        action = str(row.get("action") or "").strip()
        severity = str(row.get("severity") or "").strip()
        if not trigger:
            raise ValueError("E_PROMOTION_ROLLBACK_CRITERIA_TRIGGER_REQUIRED")
        if action != "rollback":
            raise ValueError(f"E_PROMOTION_ROLLBACK_CRITERIA_ACTION_INVALID:{trigger}")
        if severity != "blocker":
            raise ValueError(f"E_PROMOTION_ROLLBACK_CRITERIA_SEVERITY_INVALID:{trigger}")
        observed_triggers.append(trigger)

    if len(set(observed_triggers)) != len(observed_triggers):
        raise ValueError("E_PROMOTION_ROLLBACK_CRITERIA_DUPLICATE_TRIGGER")
    if {token for token in observed_triggers} != _EXPECTED_TRIGGERS:
        raise ValueError("E_PROMOTION_ROLLBACK_CRITERIA_TRIGGER_SET_MISMATCH")
    return tuple(sorted(observed_triggers))
