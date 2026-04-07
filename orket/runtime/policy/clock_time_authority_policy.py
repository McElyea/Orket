from __future__ import annotations

from typing import Any

from orket.runtime.determinism_controls import (
    CLOCK_MODE_VALUES,
    DEFAULT_CLOCK_MODE,
    DEFAULT_LOCALE,
    DEFAULT_NETWORK_MODE,
    DEFAULT_TIMEZONE,
    NETWORK_MODE_VALUES,
)


def clock_time_authority_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "authority": "orket.application.services.runtime_policy.resolve_protocol_determinism_controls",
        "defaults": {
            "timezone": DEFAULT_TIMEZONE,
            "locale": DEFAULT_LOCALE,
            "network_mode": DEFAULT_NETWORK_MODE,
            "clock_mode": DEFAULT_CLOCK_MODE,
        },
        "allowed_values": {
            "network_mode": sorted(NETWORK_MODE_VALUES),
            "clock_mode": sorted(CLOCK_MODE_VALUES),
        },
        "source_precedence": [
            "environment",
            "process_rules",
            "user_settings",
            "defaults",
        ],
        "unknown_value_behavior": {
            "network_mode": "fail_closed_error",
            "clock_mode": "fallback_default",
        },
    }


def validate_clock_time_authority_policy(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = dict(payload or clock_time_authority_policy_snapshot())
    defaults = dict(policy.get("defaults") or {})
    allowed_values = dict(policy.get("allowed_values") or {})
    network_modes = {str(token).strip() for token in allowed_values.get("network_mode", []) if str(token).strip()}
    clock_modes = {str(token).strip() for token in allowed_values.get("clock_mode", []) if str(token).strip()}
    if str(defaults.get("timezone") or "").strip() == "":
        raise ValueError("E_CLOCK_TIME_AUTHORITY_POLICY_INVALID:timezone_default_required")
    if str(defaults.get("locale") or "").strip() == "":
        raise ValueError("E_CLOCK_TIME_AUTHORITY_POLICY_INVALID:locale_default_required")
    if str(defaults.get("network_mode") or "").strip() not in network_modes:
        raise ValueError("E_CLOCK_TIME_AUTHORITY_POLICY_INVALID:network_mode_default_not_allowed")
    if str(defaults.get("clock_mode") or "").strip() not in clock_modes:
        raise ValueError("E_CLOCK_TIME_AUTHORITY_POLICY_INVALID:clock_mode_default_not_allowed")
    precedence = [str(token).strip() for token in policy.get("source_precedence", []) if str(token).strip()]
    if precedence != ["environment", "process_rules", "user_settings", "defaults"]:
        raise ValueError("E_CLOCK_TIME_AUTHORITY_POLICY_INVALID:source_precedence")
    unknown_behavior = dict(policy.get("unknown_value_behavior") or {})
    if str(unknown_behavior.get("network_mode") or "").strip() != "fail_closed_error":
        raise ValueError("E_CLOCK_TIME_AUTHORITY_POLICY_INVALID:network_mode_behavior")
    if str(unknown_behavior.get("clock_mode") or "").strip() != "fallback_default":
        raise ValueError("E_CLOCK_TIME_AUTHORITY_POLICY_INVALID:clock_mode_behavior")
    return policy
