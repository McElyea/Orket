from __future__ import annotations

from typing import Any

from orket.runtime.replay_drift_classifier import DRIFT_LAYER_PRECEDENCE

FAILURE_REPLAY_HARNESS_CONTRACT_SCHEMA_VERSION = "1.0"

_EXPECTED_REQUIRED_INPUTS = {
    "baseline_artifact",
    "candidate_artifact",
}
_EXPECTED_REQUIRED_OUTPUT_FIELDS = {
    "schema_version",
    "ok",
    "path",
    "difference_count",
    "differences",
    "drift",
}


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        token = value.strip()
        if token:
            try:
                return int(token)
            except ValueError:
                return None
    return None


def failure_replay_harness_contract_snapshot() -> dict[str, Any]:
    return {
        "schema_version": FAILURE_REPLAY_HARNESS_CONTRACT_SCHEMA_VERSION,
        "required_inputs": [
            "baseline_artifact",
            "candidate_artifact",
        ],
        "required_output_fields": [
            "schema_version",
            "ok",
            "path",
            "difference_count",
            "differences",
            "drift",
        ],
        "drift_layers": list(DRIFT_LAYER_PRECEDENCE),
        "max_reported_differences": 200,
    }


def validate_failure_replay_harness_contract(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    contract = dict(payload or failure_replay_harness_contract_snapshot())
    required_inputs = {str(token).strip() for token in contract.get("required_inputs", []) if str(token).strip()}
    if required_inputs != _EXPECTED_REQUIRED_INPUTS:
        raise ValueError("E_FAILURE_REPLAY_HARNESS_CONTRACT_REQUIRED_INPUTS_MISMATCH")

    required_output_fields = {
        str(token).strip() for token in contract.get("required_output_fields", []) if str(token).strip()
    }
    if required_output_fields != _EXPECTED_REQUIRED_OUTPUT_FIELDS:
        raise ValueError("E_FAILURE_REPLAY_HARNESS_CONTRACT_REQUIRED_OUTPUT_FIELDS_MISMATCH")

    drift_layers = tuple(str(token).strip() for token in contract.get("drift_layers", []) if str(token).strip())
    if drift_layers != DRIFT_LAYER_PRECEDENCE:
        raise ValueError("E_FAILURE_REPLAY_HARNESS_CONTRACT_DRIFT_LAYER_ORDER_MISMATCH")

    max_reported_differences = _coerce_int(contract.get("max_reported_differences"))
    if max_reported_differences is None or max_reported_differences < 1:
        raise ValueError("E_FAILURE_REPLAY_HARNESS_CONTRACT_MAX_REPORTED_DIFFERENCES_INVALID")
    return tuple(sorted(required_output_fields))
