from __future__ import annotations

from typing import Any


ARCHITECTURE_PILOT_COMPARISON_MODES = ("force_monolith", "force_microservices")


def _normalize_string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return [str(item) for item in value]


def _normalize_unlock_criterion_result(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    ok = payload.get("ok")
    failures = _normalize_string_list(payload.get("failures"))
    if not isinstance(ok, bool) or failures is None:
        return None
    if ok and failures:
        return None
    if not ok and not failures:
        return None
    normalized = dict(payload)
    normalized["ok"] = ok
    normalized["failures"] = failures
    return normalized


def _normalize_non_negative_int_map(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    normalized: dict[str, int] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            return None
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            return None
        normalized[str(key)] = int(item)
    return dict(sorted(normalized.items()))


def _normalize_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def normalize_live_acceptance_pattern_report(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    run_count = payload.get("run_count")
    session_status_counts = _normalize_non_negative_int_map(payload.get("session_status_counts"))
    pattern_counters = _normalize_non_negative_int_map(payload.get("pattern_counters"))
    invalid_payload_signals = _normalize_non_negative_int_map(payload.get("invalid_payload_signals"))

    if (
        isinstance(run_count, bool)
        or not isinstance(run_count, int)
        or run_count < 0
        or session_status_counts is None
        or pattern_counters is None
        or invalid_payload_signals is None
    ):
        return {}
    if sum(session_status_counts.values()) != run_count:
        return {}

    normalized = {
        "run_count": run_count,
        "session_status_counts": session_status_counts,
        "pattern_counters": pattern_counters,
        "invalid_payload_signals": invalid_payload_signals,
    }
    batch_id = payload.get("batch_id")
    if isinstance(batch_id, str) and batch_id.strip():
        normalized["batch_id"] = batch_id
    return normalized


def normalize_microservices_unlock_report(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    unlocked = payload.get("unlocked")
    failures = payload.get("failures")
    criteria = payload.get("criteria")
    recommended_default_builder_variant = payload.get("recommended_default_builder_variant")

    if not isinstance(unlocked, bool):
        return {}
    normalized_failures = _normalize_string_list(failures)
    if normalized_failures is None:
        return {}
    if not isinstance(criteria, dict) or not criteria:
        return {}
    normalized_criteria: dict[str, Any] = {}
    for key, value in criteria.items():
        if not isinstance(key, str) or not key.strip():
            return {}
        normalized_criterion = _normalize_unlock_criterion_result(value)
        if normalized_criterion is None:
            return {}
        normalized_criteria[str(key)] = normalized_criterion
    failing_criteria = [
        name for name, criterion in normalized_criteria.items() if not bool(criterion.get("ok"))
    ]
    if unlocked and normalized_failures:
        return {}
    if unlocked and failing_criteria:
        return {}
    if not unlocked and not normalized_failures:
        return {}
    if not unlocked and not failing_criteria:
        return {}
    for name in failing_criteria:
        prefix = f"{name}: "
        if not any(str(failure).startswith(prefix) for failure in normalized_failures):
            return {}

    normalized: dict[str, Any] = {
        "unlocked": unlocked,
        "failures": normalized_failures,
        "criteria": normalized_criteria,
    }
    if isinstance(recommended_default_builder_variant, str) and recommended_default_builder_variant.strip():
        normalized["recommended_default_builder_variant"] = recommended_default_builder_variant
    return normalized


def normalize_architecture_pilot_comparison(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    available = payload.get("available")
    if not isinstance(available, bool):
        return None
    if not available:
        return {"available": False}

    pass_delta = _normalize_float(payload.get("pass_rate_delta_microservices_minus_monolith"))
    runtime_delta = _normalize_float(payload.get("runtime_failure_rate_delta_microservices_minus_monolith"))
    reviewer_delta = _normalize_float(payload.get("reviewer_rejection_rate_delta_microservices_minus_monolith"))
    invalid_payload_failures = _normalize_string_list(payload.get("invalid_payload_failures"))
    invalid_payload_signals_by_architecture = payload.get("invalid_payload_signals_by_architecture")
    invalid_payload_signal_totals = _normalize_non_negative_int_map(
        payload.get("invalid_payload_signal_totals_by_architecture")
    )

    if (
        pass_delta is None
        or runtime_delta is None
        or reviewer_delta is None
        or invalid_payload_failures is None
        or not isinstance(invalid_payload_signals_by_architecture, dict)
        or invalid_payload_signal_totals is None
    ):
        return None

    if set(invalid_payload_signals_by_architecture.keys()) != set(ARCHITECTURE_PILOT_COMPARISON_MODES):
        return None
    if set(invalid_payload_signal_totals.keys()) != set(ARCHITECTURE_PILOT_COMPARISON_MODES):
        return None

    normalized_signals_by_architecture: dict[str, dict[str, int]] = {}
    for mode in ARCHITECTURE_PILOT_COMPARISON_MODES:
        normalized_signals = _normalize_non_negative_int_map(invalid_payload_signals_by_architecture.get(mode))
        if normalized_signals is None:
            return None
        normalized_signals_by_architecture[mode] = normalized_signals
        if sum(normalized_signals.values()) != int(invalid_payload_signal_totals.get(mode, -1)):
            return None

    return {
        "available": True,
        "pass_rate_delta_microservices_minus_monolith": pass_delta,
        "runtime_failure_rate_delta_microservices_minus_monolith": runtime_delta,
        "reviewer_rejection_rate_delta_microservices_minus_monolith": reviewer_delta,
        "invalid_payload_signals_by_architecture": normalized_signals_by_architecture,
        "invalid_payload_signal_totals_by_architecture": invalid_payload_signal_totals,
        "invalid_payload_failures": invalid_payload_failures,
    }


def _normalize_pilot_stability_check(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    stable = payload.get("stable")
    failures = _normalize_string_list(payload.get("failures"))
    if not isinstance(stable, bool) or failures is None:
        return None
    normalized = dict(payload)
    normalized["stable"] = stable
    normalized["failures"] = failures
    return normalized


def normalize_microservices_pilot_stability_report(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    stable = payload.get("stable")
    failures = payload.get("failures")
    checks = payload.get("checks")
    artifact_count = payload.get("artifact_count")
    required_consecutive = payload.get("required_consecutive")

    if not isinstance(stable, bool):
        return {}
    normalized_failures = _normalize_string_list(failures)
    if normalized_failures is None:
        return {}
    if not isinstance(checks, list):
        return {}
    if not isinstance(artifact_count, int) or artifact_count < 0:
        return {}
    if not isinstance(required_consecutive, int) or required_consecutive < 1:
        return {}

    normalized_checks = [_normalize_pilot_stability_check(item) for item in checks]
    if any(item is None for item in normalized_checks):
        return {}
    checks = [item for item in normalized_checks if item is not None]
    if artifact_count != len(checks):
        return {}
    if stable and normalized_failures:
        return {}
    if not stable and not normalized_failures:
        return {}
    if stable:
        tail = checks[-required_consecutive:]
        if len(tail) != required_consecutive or not all(bool(item.get("stable")) for item in tail):
            return {}

    normalized = dict(payload)
    normalized["failures"] = normalized_failures
    normalized["checks"] = checks
    return normalized
