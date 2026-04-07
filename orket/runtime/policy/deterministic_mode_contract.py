from __future__ import annotations

import os
from typing import Any

DETERMINISTIC_MODE_CONTRACT_SCHEMA_VERSION = "1.0"

_DETERMINISTIC_ENV_KEYS = (
    "ORKET_DETERMINISTIC_MODE",
    "ORKET_PROTOCOL_DETERMINISTIC_MODE",
    "ORKET_RUNTIME_DETERMINISTIC_MODE",
)


def _parse_bool(value: Any) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def resolve_deterministic_mode_flag(*, environment: dict[str, str] | None = None) -> tuple[bool, str]:
    env = environment if isinstance(environment, dict) else dict(os.environ)
    for key in _DETERMINISTIC_ENV_KEYS:
        parsed = _parse_bool(env.get(key))
        if parsed is None:
            continue
        return parsed, key
    return False, "default"


def deterministic_mode_contract_snapshot(*, environment: dict[str, str] | None = None) -> dict[str, object]:
    enabled, source = resolve_deterministic_mode_flag(environment=environment)
    return {
        "schema_version": DETERMINISTIC_MODE_CONTRACT_SCHEMA_VERSION,
        "deterministic_mode_enabled": bool(enabled),
        "resolution_source": source,
        "env_keys_considered": list(_DETERMINISTIC_ENV_KEYS),
        "behavior_contract": {
            "optional_heuristics": "disabled" if enabled else "enabled",
            "retry_policy": "minimal_required" if enabled else "adaptive_retries",
            "fallback_policy": "policy_required_only" if enabled else "policy_and_heuristic",
        },
    }
