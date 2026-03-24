from __future__ import annotations

from typing import Any

from orket.runtime.protocol_error_codes import (
    E_CAPABILITY_VIOLATION_PREFIX,
    E_DETERMINISM_POLICY_VIOLATION_PREFIX,
    E_NAMESPACE_POLICY_VIOLATION_PREFIX,
    E_RING_POLICY_VIOLATION_PREFIX,
    E_TOOL_INVOCATION_BOUNDARY_PREFIX,
    is_registered_protocol_error_code,
)


TOOL_INVOCATION_POLICY_CONTRACT_SCHEMA_VERSION = "1.0"

_ALLOWED_TOOL_RINGS = {
    "core",
    "compatibility",
    "experimental",
}
_ALLOWED_CAPABILITY_PROFILES = {
    "workspace",
    "external",
}
_ALLOWED_DETERMINISM_CLASSES = {
    "pure",
    "workspace",
    "external",
}
_ALLOWED_NAMESPACE_SCOPE_RULES = {
    "run_scope_only",
    "declared_scope_subset",
}
_ALLOWED_TOOL_TO_TOOL_POLICY = {
    "disallow",
}
_EXPECTED_RUN_TYPES = {
    "epic",
}


def tool_invocation_policy_contract_snapshot() -> dict[str, Any]:
    return {
        "schema_version": TOOL_INVOCATION_POLICY_CONTRACT_SCHEMA_VERSION,
        "policies": [
            {
                "run_type": "epic",
                "route_lane": "core_epic",
                "allowed_tool_rings": [
                    "core",
                ],
                "allowed_capability_profiles": [
                    "workspace",
                ],
                "namespace_scope_rule": "run_scope_only",
                "run_determinism_class": "workspace",
                "tool_to_tool_invocation": "disallow",
                "max_tool_invocations_per_run": 200,
                "required_error_codes": [
                    E_RING_POLICY_VIOLATION_PREFIX,
                    E_CAPABILITY_VIOLATION_PREFIX,
                    E_NAMESPACE_POLICY_VIOLATION_PREFIX,
                    E_DETERMINISM_POLICY_VIOLATION_PREFIX,
                    E_TOOL_INVOCATION_BOUNDARY_PREFIX,
                ],
            }
        ],
    }


def validate_tool_invocation_policy_contract(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    contract = dict(payload or tool_invocation_policy_contract_snapshot())
    rows = list(contract.get("policies") or [])
    if not rows:
        raise ValueError("E_TOOL_INVOCATION_POLICY_CONTRACT_EMPTY")

    observed_run_types: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_TOOL_INVOCATION_POLICY_CONTRACT_ROW_SCHEMA")
        run_type = str(row.get("run_type") or "").strip().lower()
        route_lane = str(row.get("route_lane") or "").strip()
        allowed_tool_rings = {
            str(token).strip().lower() for token in list(row.get("allowed_tool_rings") or []) if str(token).strip()
        }
        allowed_capability_profiles = {
            str(token).strip().lower()
            for token in list(row.get("allowed_capability_profiles") or [])
            if str(token).strip()
        }
        namespace_scope_rule = str(row.get("namespace_scope_rule") or "").strip().lower()
        run_determinism_class = str(row.get("run_determinism_class") or "").strip().lower()
        tool_to_tool_invocation = str(row.get("tool_to_tool_invocation") or "").strip().lower()
        max_tool_invocations_per_run = int(row.get("max_tool_invocations_per_run") or 0)
        required_error_codes = [
            str(token).strip() for token in list(row.get("required_error_codes") or []) if str(token).strip()
        ]

        if not run_type:
            raise ValueError("E_TOOL_INVOCATION_POLICY_CONTRACT_RUN_TYPE_REQUIRED")
        if not route_lane:
            raise ValueError(f"E_TOOL_INVOCATION_POLICY_CONTRACT_ROUTE_LANE_REQUIRED:{run_type}")
        if not allowed_tool_rings:
            raise ValueError(f"E_TOOL_INVOCATION_POLICY_CONTRACT_RINGS_EMPTY:{run_type}")
        if not allowed_tool_rings.issubset(_ALLOWED_TOOL_RINGS):
            raise ValueError(f"E_TOOL_INVOCATION_POLICY_CONTRACT_RING_INVALID:{run_type}")
        if not allowed_capability_profiles:
            raise ValueError(f"E_TOOL_INVOCATION_POLICY_CONTRACT_CAPABILITY_PROFILES_EMPTY:{run_type}")
        if not allowed_capability_profiles.issubset(_ALLOWED_CAPABILITY_PROFILES):
            raise ValueError(f"E_TOOL_INVOCATION_POLICY_CONTRACT_CAPABILITY_PROFILE_INVALID:{run_type}")
        if namespace_scope_rule not in _ALLOWED_NAMESPACE_SCOPE_RULES:
            raise ValueError(f"E_TOOL_INVOCATION_POLICY_CONTRACT_NAMESPACE_SCOPE_RULE_INVALID:{run_type}")
        if run_determinism_class not in _ALLOWED_DETERMINISM_CLASSES:
            raise ValueError(f"E_TOOL_INVOCATION_POLICY_CONTRACT_DETERMINISM_CLASS_INVALID:{run_type}")
        if tool_to_tool_invocation not in _ALLOWED_TOOL_TO_TOOL_POLICY:
            raise ValueError(f"E_TOOL_INVOCATION_POLICY_CONTRACT_TOOL_TO_TOOL_POLICY_INVALID:{run_type}")
        if max_tool_invocations_per_run <= 0:
            raise ValueError(f"E_TOOL_INVOCATION_POLICY_CONTRACT_MAX_INVOCATIONS_INVALID:{run_type}")
        if not required_error_codes:
            raise ValueError(f"E_TOOL_INVOCATION_POLICY_CONTRACT_REQUIRED_ERROR_CODES_EMPTY:{run_type}")
        if any(not is_registered_protocol_error_code(code) for code in required_error_codes):
            raise ValueError(f"E_TOOL_INVOCATION_POLICY_CONTRACT_REQUIRED_ERROR_CODE_UNREGISTERED:{run_type}")

        observed_run_types.append(run_type)

    if len(set(observed_run_types)) != len(observed_run_types):
        raise ValueError("E_TOOL_INVOCATION_POLICY_CONTRACT_DUPLICATE_RUN_TYPE")
    if set(observed_run_types) != _EXPECTED_RUN_TYPES:
        raise ValueError("E_TOOL_INVOCATION_POLICY_CONTRACT_RUN_TYPE_SET_MISMATCH")
    return tuple(sorted(observed_run_types))
