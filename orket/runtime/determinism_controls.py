from __future__ import annotations

import os
from typing import Any

from orket.application.workflows.protocol_hashing import (
    hash_clock_artifact_ref,
    hash_env_allowlist,
    hash_network_allowlist,
)
from orket.runtime.protocol_error_codes import E_NETWORK_MODE_INVALID_PREFIX

DEFAULT_TIMEZONE = "UTC"
DEFAULT_LOCALE = "C.UTF-8"
DEFAULT_NETWORK_MODE = "off"
DEFAULT_CLOCK_MODE = "wall"
NETWORK_MODE_VALUES = {"off", "allowlist"}
CLOCK_MODE_VALUES = {"wall", "artifact_replay"}


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def resolve_timezone(*values: Any) -> str:
    for value in values:
        normalized = _normalize(value)
        if normalized:
            return normalized
    return DEFAULT_TIMEZONE


def resolve_locale(*values: Any) -> str:
    for value in values:
        normalized = _normalize(value)
        if normalized:
            return normalized
    return DEFAULT_LOCALE


def resolve_network_mode(*values: Any) -> str:
    for value in values:
        normalized = _normalize(value).lower().replace("-", "_")
        if not normalized:
            continue
        aliases = {
            "off": "off",
            "offline": "off",
            "disabled": "off",
            "allowlist": "allowlist",
            "allow_list": "allowlist",
            "online_allowlist": "allowlist",
        }
        resolved = aliases.get(normalized)
        if resolved is None:
            raise ValueError(
                f"{E_NETWORK_MODE_INVALID_PREFIX}:{normalized} (expected one of: {sorted(NETWORK_MODE_VALUES)})"
            )
        return resolved
    return DEFAULT_NETWORK_MODE


def parse_network_allowlist(value: Any) -> list[str]:
    if isinstance(value, list):
        tokens = [str(item).strip() for item in value if str(item).strip()]
        return sorted(set(tokens))
    raw = _normalize(value)
    if not raw:
        return []
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    return sorted(set(tokens))


def resolve_network_allowlist(*values: Any) -> list[str]:
    for value in values:
        parsed = parse_network_allowlist(value)
        if parsed:
            return parsed
    return []


def resolve_clock_mode(*values: Any) -> str:
    for value in values:
        normalized = _normalize(value).lower().replace("-", "_")
        if not normalized:
            continue
        aliases = {
            "wall": "wall",
            "wall_clock": "wall",
            "artifact_replay": "artifact_replay",
            "artifact": "artifact_replay",
            "replay": "artifact_replay",
            "captured": "artifact_replay",
        }
        resolved = aliases.get(normalized)
        if resolved is None:
            continue
        return resolved
    return DEFAULT_CLOCK_MODE


def resolve_clock_artifact_ref(*values: Any) -> str:
    for value in values:
        normalized = _normalize(value)
        if normalized:
            return normalized
    return ""


def parse_env_allowlist(value: Any) -> list[str]:
    if isinstance(value, list):
        tokens = [str(item).strip() for item in value if str(item).strip()]
        return sorted(set(tokens))
    raw = _normalize(value)
    if not raw:
        return []
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    return sorted(set(tokens))


def resolve_env_allowlist(*values: Any) -> list[str]:
    for value in values:
        parsed = parse_env_allowlist(value)
        if parsed:
            return parsed
    return []


def snapshot_env_allowlist(*, allowlist: list[str], environment: dict[str, str] | None = None) -> dict[str, str]:
    env = environment if isinstance(environment, dict) else dict(os.environ)
    snapshot: dict[str, str] = {}
    for key in sorted({str(name).strip() for name in allowlist if str(name).strip()}):
        if key in env:
            snapshot[key] = str(env[key])
    return snapshot


def build_determinism_controls(
    *,
    timezone: Any = None,
    locale: Any = None,
    network_mode: Any = None,
    network_allowlist: Any = None,
    clock_mode: Any = None,
    clock_artifact_ref: Any = None,
    env_allowlist: Any = None,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    resolved_timezone = resolve_timezone(timezone)
    resolved_locale = resolve_locale(locale)
    resolved_network_mode = resolve_network_mode(network_mode)
    resolved_network_allowlist = resolve_network_allowlist(network_allowlist)
    resolved_clock_mode = resolve_clock_mode(clock_mode)
    resolved_clock_artifact_ref = resolve_clock_artifact_ref(clock_artifact_ref)
    resolved_allowlist = resolve_env_allowlist(env_allowlist)
    env_snapshot = snapshot_env_allowlist(allowlist=resolved_allowlist, environment=environment)
    return {
        "timezone": resolved_timezone,
        "locale": resolved_locale,
        "network_mode": resolved_network_mode,
        "network_allowlist": resolved_network_allowlist,
        "network_allowlist_hash": hash_network_allowlist(resolved_network_allowlist),
        "clock_mode": resolved_clock_mode,
        "clock_artifact_ref": resolved_clock_artifact_ref,
        "clock_artifact_hash": hash_clock_artifact_ref(resolved_clock_artifact_ref),
        "env_allowlist": resolved_allowlist,
        "env_snapshot": env_snapshot,
        "env_allowlist_hash": hash_env_allowlist(env_snapshot),
    }
