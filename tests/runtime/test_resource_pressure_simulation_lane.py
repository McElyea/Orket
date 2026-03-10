from __future__ import annotations

import pytest

from orket.runtime.resource_pressure_simulation_lane import (
    resource_pressure_simulation_lane_snapshot,
    validate_resource_pressure_simulation_lane,
)


# Layer: unit
def test_resource_pressure_simulation_lane_snapshot_contains_expected_check_ids() -> None:
    payload = resource_pressure_simulation_lane_snapshot()
    assert payload["schema_version"] == "1.0"
    check_ids = {row["check_id"] for row in payload["checks"]}
    assert check_ids == {
        "cpu_pressure_high_delta_volume",
        "memory_pressure_large_chunk_payload",
        "latency_pressure_delayed_deltas",
    }


# Layer: contract
def test_validate_resource_pressure_simulation_lane_accepts_current_snapshot() -> None:
    check_ids = validate_resource_pressure_simulation_lane()
    assert "cpu_pressure_high_delta_volume" in check_ids


# Layer: contract
def test_validate_resource_pressure_simulation_lane_rejects_missing_check() -> None:
    payload = resource_pressure_simulation_lane_snapshot()
    payload["checks"] = [row for row in payload["checks"] if row["check_id"] != "latency_pressure_delayed_deltas"]
    with pytest.raises(ValueError, match="E_RESOURCE_PRESSURE_SIMULATION_LANE_CHECK_ID_SET_MISMATCH"):
        _ = validate_resource_pressure_simulation_lane(payload)


# Layer: contract
def test_validate_resource_pressure_simulation_lane_rejects_negative_delay() -> None:
    payload = resource_pressure_simulation_lane_snapshot()
    payload["checks"][0]["input_config"]["delta_delay_ms"] = -1
    with pytest.raises(ValueError, match="E_RESOURCE_PRESSURE_SIMULATION_LANE_DELTA_DELAY_INVALID"):
        _ = validate_resource_pressure_simulation_lane(payload)
