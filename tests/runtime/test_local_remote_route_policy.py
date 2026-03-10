from __future__ import annotations

import pytest

from orket.runtime.local_remote_route_policy import (
    local_remote_route_policy_snapshot,
    validate_local_remote_route_policy,
)


# Layer: unit
def test_local_remote_route_policy_snapshot_contains_expected_lanes() -> None:
    payload = local_remote_route_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    lanes = {row["route_lane"] for row in payload["lanes"]}
    assert lanes == {
        "core_epic",
        "protocol_governed",
        "maintenance",
        "research",
    }


# Layer: contract
def test_validate_local_remote_route_policy_accepts_current_snapshot() -> None:
    lanes = validate_local_remote_route_policy()
    assert "core_epic" in lanes


# Layer: contract
def test_validate_local_remote_route_policy_rejects_lane_set_mismatch() -> None:
    payload = local_remote_route_policy_snapshot()
    payload["lanes"] = [row for row in payload["lanes"] if row["route_lane"] != "research"]
    with pytest.raises(ValueError, match="E_LOCAL_REMOTE_ROUTE_POLICY_LANE_SET_MISMATCH"):
        _ = validate_local_remote_route_policy(payload)
