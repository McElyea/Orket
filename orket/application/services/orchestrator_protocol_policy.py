from __future__ import annotations

from typing import Any

from orket.application.services.runtime_policy import (
    resolve_protocol_determinism_controls,
)
from orket.runtime.config import settings


def _selected_protocol_value(name: str, *, process_rules: dict[str, Any], user_settings: dict[str, Any]) -> str:
    return settings.resolve_str(
        "ORKET_PROTOCOL_" + name.upper(),
        process_rules=process_rules,
        process_key="protocol_" + name,
        user_key="protocol_" + name,
        user_settings=user_settings,
    )


def select_protocol_governed_enabled(*, user_settings: dict[str, Any], process_rules: dict[str, Any]) -> bool:
    return bool(
        settings.resolve_bool(
            "ORKET_PROTOCOL_GOVERNED_ENABLED",
            "ORKET_PROTOCOL_GOVERNED",
            process_rules=process_rules,
            process_key="protocol_governed_enabled",
            user_key="protocol_governed_enabled",
            user_settings=user_settings,
            default=False,
        )
    )


def select_protocol_max_response_bytes(*, user_settings: dict[str, Any], process_rules: dict[str, Any]) -> int:
    raw = settings.resolve_str(
        "ORKET_PROTOCOL_MAX_RESPONSE_BYTES",
        process_rules=process_rules,
        process_key="protocol_max_response_bytes",
        user_key="protocol_max_response_bytes",
        user_settings=user_settings,
    )
    if raw:
        try:
            return max(256, int(raw))
        except (TypeError, ValueError):
            pass
    return 8192


def select_protocol_max_tool_calls(*, user_settings: dict[str, Any], process_rules: dict[str, Any]) -> int:
    raw = settings.resolve_str(
        "ORKET_PROTOCOL_MAX_TOOL_CALLS",
        process_rules=process_rules,
        process_key="protocol_max_tool_calls",
        user_key="protocol_max_tool_calls",
        user_settings=user_settings,
    )
    if raw:
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            pass
    return 8


def select_protocol_determinism_context(
    *, user_settings: dict[str, Any], process_rules: dict[str, Any]
) -> dict[str, Any]:
    controls = resolve_protocol_determinism_controls(
        timezone_values=[
            _selected_protocol_value("timezone", process_rules=process_rules, user_settings=user_settings)
        ],
        locale_values=[_selected_protocol_value("locale", process_rules=process_rules, user_settings=user_settings)],
        network_mode_values=[
            _selected_protocol_value("network_mode", process_rules=process_rules, user_settings=user_settings)
        ],
        network_allowlist_values=[
            _selected_protocol_value("network_allowlist", process_rules=process_rules, user_settings=user_settings)
        ],
        clock_mode_values=[
            _selected_protocol_value("clock_mode", process_rules=process_rules, user_settings=user_settings)
        ],
        clock_artifact_ref_values=[
            _selected_protocol_value("clock_artifact_ref", process_rules=process_rules, user_settings=user_settings)
        ],
        env_allowlist_values=[
            _selected_protocol_value("env_allowlist", process_rules=process_rules, user_settings=user_settings)
        ],
    )
    return {
        "timezone": str(controls.get("timezone") or "UTC"),
        "locale": str(controls.get("locale") or "C.UTF-8"),
        "network_mode": str(controls.get("network_mode") or "off"),
        "network_allowlist_values": list(controls.get("network_allowlist") or []),
        "network_allowlist_hash": str(controls.get("network_allowlist_hash") or ""),
        "clock_mode": str(controls.get("clock_mode") or "wall"),
        "clock_artifact_ref": str(controls.get("clock_artifact_ref") or ""),
        "clock_artifact_hash": str(controls.get("clock_artifact_hash") or ""),
        "env_allowlist": dict(controls.get("env_snapshot") or {}),
        "env_allowlist_values": list(controls.get("env_allowlist") or []),
        "env_allowlist_hash": str(controls.get("env_allowlist_hash") or ""),
    }
