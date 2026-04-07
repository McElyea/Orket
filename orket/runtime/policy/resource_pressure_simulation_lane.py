from __future__ import annotations

from typing import Any

RESOURCE_PRESSURE_SIMULATION_LANE_SCHEMA_VERSION = "1.0"

_EXPECTED_CHECK_IDS = {
    "cpu_pressure_high_delta_volume",
    "memory_pressure_large_chunk_payload",
    "latency_pressure_delayed_deltas",
}


def resource_pressure_simulation_lane_snapshot() -> dict[str, Any]:
    return {
        "schema_version": RESOURCE_PRESSURE_SIMULATION_LANE_SCHEMA_VERSION,
        "target_surface": "orket.streaming.model_provider.StubModelStreamProvider",
        "checks": [
            {
                "check_id": "cpu_pressure_high_delta_volume",
                "input_config": {
                    "delta_count": 800,
                    "chunk_size": 1,
                    "delta_delay_ms": 0,
                },
                "min_token_delta_count": 800,
                "max_elapsed_ms": 3000,
            },
            {
                "check_id": "memory_pressure_large_chunk_payload",
                "input_config": {
                    "delta_count": 120,
                    "chunk_size": 64,
                    "delta_delay_ms": 0,
                },
                "min_token_delta_count": 120,
                "max_elapsed_ms": 2500,
            },
            {
                "check_id": "latency_pressure_delayed_deltas",
                "input_config": {
                    "delta_count": 60,
                    "chunk_size": 2,
                    "delta_delay_ms": 1,
                    "first_token_delay_ms": 5,
                },
                "min_token_delta_count": 60,
                "max_elapsed_ms": 4000,
            },
        ],
    }


def validate_resource_pressure_simulation_lane(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    contract = dict(payload or resource_pressure_simulation_lane_snapshot())
    target_surface = str(contract.get("target_surface") or "").strip()
    if not target_surface:
        raise ValueError("E_RESOURCE_PRESSURE_SIMULATION_LANE_SURFACE_REQUIRED")

    checks = list(contract.get("checks") or [])
    if not checks:
        raise ValueError("E_RESOURCE_PRESSURE_SIMULATION_LANE_EMPTY")

    observed_check_ids: list[str] = []
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError("E_RESOURCE_PRESSURE_SIMULATION_LANE_ROW_SCHEMA")
        check_id = str(row.get("check_id") or "").strip()
        if not check_id:
            raise ValueError("E_RESOURCE_PRESSURE_SIMULATION_LANE_CHECK_ID_REQUIRED")
        input_config = row.get("input_config")
        if not isinstance(input_config, dict):
            raise ValueError(f"E_RESOURCE_PRESSURE_SIMULATION_LANE_INPUT_CONFIG_SCHEMA:{check_id}")
        _coerce_positive_int(
            input_config.get("delta_count"),
            error_code=f"E_RESOURCE_PRESSURE_SIMULATION_LANE_DELTA_COUNT_INVALID:{check_id}",
        )
        _coerce_positive_int(
            input_config.get("chunk_size"),
            error_code=f"E_RESOURCE_PRESSURE_SIMULATION_LANE_CHUNK_SIZE_INVALID:{check_id}",
        )
        _coerce_non_negative_int(
            input_config.get("delta_delay_ms"),
            error_code=f"E_RESOURCE_PRESSURE_SIMULATION_LANE_DELTA_DELAY_INVALID:{check_id}",
        )
        _coerce_non_negative_int(
            input_config.get("first_token_delay_ms", 0),
            error_code=f"E_RESOURCE_PRESSURE_SIMULATION_LANE_FIRST_TOKEN_DELAY_INVALID:{check_id}",
        )
        _coerce_positive_int(
            row.get("min_token_delta_count"),
            error_code=f"E_RESOURCE_PRESSURE_SIMULATION_LANE_MIN_TOKENS_INVALID:{check_id}",
        )
        _coerce_positive_int(
            row.get("max_elapsed_ms"),
            error_code=f"E_RESOURCE_PRESSURE_SIMULATION_LANE_MAX_ELAPSED_INVALID:{check_id}",
        )
        observed_check_ids.append(check_id)

    if len(set(observed_check_ids)) != len(observed_check_ids):
        raise ValueError("E_RESOURCE_PRESSURE_SIMULATION_LANE_DUPLICATE_CHECK_ID")
    if set(observed_check_ids) != _EXPECTED_CHECK_IDS:
        raise ValueError("E_RESOURCE_PRESSURE_SIMULATION_LANE_CHECK_ID_SET_MISMATCH")
    return tuple(sorted(observed_check_ids))


def _coerce_positive_int(value: Any, *, error_code: str) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(error_code) from exc
    if resolved < 1:
        raise ValueError(error_code)
    return resolved


def _coerce_non_negative_int(value: Any, *, error_code: str) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(error_code) from exc
    if resolved < 0:
        raise ValueError(error_code)
    return resolved
