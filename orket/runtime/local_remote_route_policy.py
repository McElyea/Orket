from __future__ import annotations

from typing import Any


LOCAL_REMOTE_ROUTE_POLICY_SCHEMA_VERSION = "1.0"

_EXPECTED_ROUTE_LANES = {
    "core_epic",
    "protocol_governed",
    "maintenance",
    "research",
}
_ALLOWED_ROUTE_TARGETS = {
    "none",
    "local",
    "remote",
}
_ALLOWED_REMOTE_ROUTE_POLICIES = {
    "disallow",
    "require_override",
    "allow",
}


def local_remote_route_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": LOCAL_REMOTE_ROUTE_POLICY_SCHEMA_VERSION,
        "lanes": [
            {
                "route_lane": "core_epic",
                "default_route_target": "local",
                "fallback_route_target": "none",
                "remote_route_policy": "disallow",
                "required_route_artifacts": [
                    "route_decision_artifact",
                    "capability_manifest",
                ],
            },
            {
                "route_lane": "protocol_governed",
                "default_route_target": "local",
                "fallback_route_target": "none",
                "remote_route_policy": "require_override",
                "required_route_artifacts": [
                    "route_decision_artifact",
                    "operator_override_log",
                ],
            },
            {
                "route_lane": "maintenance",
                "default_route_target": "local",
                "fallback_route_target": "local",
                "remote_route_policy": "require_override",
                "required_route_artifacts": [
                    "route_decision_artifact",
                    "operator_override_log",
                ],
            },
            {
                "route_lane": "research",
                "default_route_target": "remote",
                "fallback_route_target": "local",
                "remote_route_policy": "allow",
                "required_route_artifacts": [
                    "route_decision_artifact",
                    "source_attribution",
                ],
            },
        ],
    }


def validate_local_remote_route_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or local_remote_route_policy_snapshot())
    rows = list(policy.get("lanes") or [])
    if not rows:
        raise ValueError("E_LOCAL_REMOTE_ROUTE_POLICY_EMPTY")

    observed_lanes: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_LOCAL_REMOTE_ROUTE_POLICY_ROW_SCHEMA")
        route_lane = str(row.get("route_lane") or "").strip()
        default_route_target = str(row.get("default_route_target") or "").strip()
        fallback_route_target = str(row.get("fallback_route_target") or "").strip()
        remote_route_policy = str(row.get("remote_route_policy") or "").strip()
        required_route_artifacts = [
            str(token).strip() for token in row.get("required_route_artifacts", []) if str(token).strip()
        ]
        if not route_lane:
            raise ValueError("E_LOCAL_REMOTE_ROUTE_POLICY_LANE_REQUIRED")
        if default_route_target not in _ALLOWED_ROUTE_TARGETS - {"none"}:
            raise ValueError(f"E_LOCAL_REMOTE_ROUTE_POLICY_DEFAULT_TARGET_INVALID:{route_lane}")
        if fallback_route_target not in _ALLOWED_ROUTE_TARGETS:
            raise ValueError(f"E_LOCAL_REMOTE_ROUTE_POLICY_FALLBACK_TARGET_INVALID:{route_lane}")
        if remote_route_policy not in _ALLOWED_REMOTE_ROUTE_POLICIES:
            raise ValueError(f"E_LOCAL_REMOTE_ROUTE_POLICY_REMOTE_POLICY_INVALID:{route_lane}")
        if not required_route_artifacts:
            raise ValueError(f"E_LOCAL_REMOTE_ROUTE_POLICY_REQUIRED_ARTIFACTS_EMPTY:{route_lane}")
        observed_lanes.append(route_lane)

    if len(set(observed_lanes)) != len(observed_lanes):
        raise ValueError("E_LOCAL_REMOTE_ROUTE_POLICY_DUPLICATE_LANE")
    if set(observed_lanes) != _EXPECTED_ROUTE_LANES:
        raise ValueError("E_LOCAL_REMOTE_ROUTE_POLICY_LANE_SET_MISMATCH")
    return tuple(sorted(observed_lanes))
