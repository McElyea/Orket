from __future__ import annotations

from typing import Any


NON_FATAL_ERROR_BUDGET_SCHEMA_VERSION = "1.0"

_EXPECTED_BUDGET_IDS = {
    "degraded_completion_ratio",
    "repair_applied_ratio",
    "timeout_recovery_ratio",
    "non_fatal_validation_error_ratio",
}
_ALLOWED_BREACH_ACTIONS = {
    "hold_promotion",
    "raise_alert",
}


def non_fatal_error_budget_snapshot() -> dict[str, Any]:
    return {
        "schema_version": NON_FATAL_ERROR_BUDGET_SCHEMA_VERSION,
        "evaluation_window": {
            "lookback_runs": 200,
            "window_hours": 24,
            "min_distinct_runs": 100,
        },
        "budgets": [
            {
                "budget_id": "degraded_completion_ratio",
                "metric": "run_status.degraded",
                "max_fraction": 0.05,
                "breach_action": "hold_promotion",
            },
            {
                "budget_id": "repair_applied_ratio",
                "metric": "repair.disposition.applied",
                "max_fraction": 0.08,
                "breach_action": "hold_promotion",
            },
            {
                "budget_id": "timeout_recovery_ratio",
                "metric": "timeout.degraded_recovery",
                "max_fraction": 0.03,
                "breach_action": "raise_alert",
            },
            {
                "budget_id": "non_fatal_validation_error_ratio",
                "metric": "validation.non_fatal_error",
                "max_fraction": 0.02,
                "breach_action": "raise_alert",
            },
        ],
        "escalation_policy": {
            "consecutive_breaches_for_escalation": 2,
            "escalation_action": "require_operator_override",
        },
    }


def validate_non_fatal_error_budget(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    budget = dict(payload or non_fatal_error_budget_snapshot())
    _validate_evaluation_window(budget.get("evaluation_window"))
    _validate_escalation_policy(budget.get("escalation_policy"))

    rows = list(budget.get("budgets") or [])
    if not rows:
        raise ValueError("E_NON_FATAL_ERROR_BUDGET_EMPTY")

    observed_budget_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_NON_FATAL_ERROR_BUDGET_ROW_SCHEMA")
        budget_id = str(row.get("budget_id") or "").strip()
        metric = str(row.get("metric") or "").strip()
        max_fraction = _coerce_fraction(row.get("max_fraction"), error_code="E_NON_FATAL_ERROR_BUDGET_MAX_FRACTION_INVALID")
        breach_action = str(row.get("breach_action") or "").strip()
        if not budget_id:
            raise ValueError("E_NON_FATAL_ERROR_BUDGET_ID_REQUIRED")
        if not metric:
            raise ValueError(f"E_NON_FATAL_ERROR_BUDGET_METRIC_REQUIRED:{budget_id}")
        if max_fraction <= 0.0 or max_fraction >= 1.0:
            raise ValueError(f"E_NON_FATAL_ERROR_BUDGET_MAX_FRACTION_RANGE:{budget_id}")
        if breach_action not in _ALLOWED_BREACH_ACTIONS:
            raise ValueError(f"E_NON_FATAL_ERROR_BUDGET_BREACH_ACTION_INVALID:{budget_id}")
        observed_budget_ids.append(budget_id)

    if len(set(observed_budget_ids)) != len(observed_budget_ids):
        raise ValueError("E_NON_FATAL_ERROR_BUDGET_DUPLICATE_ID")
    if set(observed_budget_ids) != _EXPECTED_BUDGET_IDS:
        raise ValueError("E_NON_FATAL_ERROR_BUDGET_ID_SET_MISMATCH")
    return tuple(sorted(observed_budget_ids))


def _validate_evaluation_window(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("E_NON_FATAL_ERROR_BUDGET_WINDOW_SCHEMA")
    _coerce_positive_int(payload.get("lookback_runs"), error_code="E_NON_FATAL_ERROR_BUDGET_LOOKBACK_RUNS_INVALID")
    _coerce_positive_int(payload.get("window_hours"), error_code="E_NON_FATAL_ERROR_BUDGET_WINDOW_HOURS_INVALID")
    _coerce_positive_int(
        payload.get("min_distinct_runs"),
        error_code="E_NON_FATAL_ERROR_BUDGET_MIN_DISTINCT_RUNS_INVALID",
    )


def _validate_escalation_policy(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("E_NON_FATAL_ERROR_BUDGET_ESCALATION_POLICY_SCHEMA")
    consecutive_breaches = _coerce_positive_int(
        payload.get("consecutive_breaches_for_escalation"),
        error_code="E_NON_FATAL_ERROR_BUDGET_CONSECUTIVE_BREACHES_INVALID",
    )
    escalation_action = str(payload.get("escalation_action") or "").strip()
    if consecutive_breaches < 2:
        raise ValueError("E_NON_FATAL_ERROR_BUDGET_CONSECUTIVE_BREACHES_RANGE")
    if escalation_action != "require_operator_override":
        raise ValueError("E_NON_FATAL_ERROR_BUDGET_ESCALATION_ACTION_INVALID")


def _coerce_positive_int(value: Any, *, error_code: str) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(error_code) from exc
    if resolved < 1:
        raise ValueError(error_code)
    return resolved


def _coerce_fraction(value: Any, *, error_code: str) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(error_code) from exc
    return resolved
