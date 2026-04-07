from __future__ import annotations

from typing import Any

from orket.runtime.determinism_controls import (
    DEFAULT_CLOCK_MODE,
    DEFAULT_LOCALE,
    DEFAULT_NETWORK_MODE,
    DEFAULT_TIMEZONE,
)
from orket.runtime.deterministic_mode_contract import resolve_deterministic_mode_flag
from orket.runtime.provider_runtime_target import effective_provider
from orket.runtime.unknown_input_policy import unknown_input_policy_snapshot


def safe_default_catalog_snapshot() -> dict[str, Any]:
    deterministic_mode_enabled, _ = resolve_deterministic_mode_flag(environment={})
    surfaces_payload = unknown_input_policy_snapshot().get("surfaces")
    surfaces = surfaces_payload if isinstance(surfaces_payload, list) else []
    unknown_input_surfaces = {
        str(row.get("surface") or "").strip(): str(row.get("on_unknown") or "").strip()
        for row in surfaces
        if isinstance(row, dict)
    }
    rows = [
        {
            "default_key": "protocol_timezone",
            "default_value": DEFAULT_TIMEZONE,
            "owner": "orket/runtime/determinism_controls.py",
        },
        {
            "default_key": "protocol_locale",
            "default_value": DEFAULT_LOCALE,
            "owner": "orket/runtime/determinism_controls.py",
        },
        {
            "default_key": "protocol_network_mode",
            "default_value": DEFAULT_NETWORK_MODE,
            "owner": "orket/runtime/determinism_controls.py",
        },
        {
            "default_key": "protocol_clock_mode",
            "default_value": DEFAULT_CLOCK_MODE,
            "owner": "orket/runtime/determinism_controls.py",
        },
        {
            "default_key": "deterministic_mode_enabled",
            "default_value": bool(deterministic_mode_enabled),
            "owner": "orket/runtime/deterministic_mode_contract.py",
        },
        {
            "default_key": "provider_runtime_target.default_provider",
            "default_value": effective_provider(None, default="ollama"),
            "owner": "orket/runtime/provider_runtime_target.py",
        },
        {
            "default_key": "unknown_provider_input.on_unknown",
            "default_value": unknown_input_surfaces.get("provider_runtime_target.requested_provider", ""),
            "owner": "orket/runtime/unknown_input_policy.py",
        },
    ]
    return {
        "schema_version": "1.0",
        "defaults": rows,
    }


def validate_safe_default_catalog(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    catalog = dict(payload or safe_default_catalog_snapshot())
    defaults_payload = catalog.get("defaults")
    rows = defaults_payload if isinstance(defaults_payload, list) else []
    if not rows:
        raise ValueError("E_SAFE_DEFAULT_CATALOG_EMPTY")
    keys: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_SAFE_DEFAULT_CATALOG_ROW_SCHEMA")
        key = str(row.get("default_key") or "").strip()
        owner = str(row.get("owner") or "").strip()
        if not key or not owner:
            raise ValueError("E_SAFE_DEFAULT_CATALOG_ROW_SCHEMA")
        value = row.get("default_value")
        if value is None:
            raise ValueError(f"E_SAFE_DEFAULT_CATALOG_VALUE_REQUIRED:{key}")
        if isinstance(value, str) and not value.strip():
            raise ValueError(f"E_SAFE_DEFAULT_CATALOG_VALUE_REQUIRED:{key}")
        keys.append(key)
    if len(set(keys)) != len(keys):
        raise ValueError("E_SAFE_DEFAULT_CATALOG_DUPLICATE_KEY")
    provider_unknown = next(
        (
            row
            for row in rows
            if isinstance(row, dict) and str(row.get("default_key") or "").strip() == "unknown_provider_input.on_unknown"
        ),
        None,
    )
    if not isinstance(provider_unknown, dict) or str(provider_unknown.get("default_value") or "").strip() != "fail_closed":
        raise ValueError("E_SAFE_DEFAULT_CATALOG_PROVIDER_UNKNOWN_NOT_FAIL_CLOSED")
    return tuple(sorted(keys))
