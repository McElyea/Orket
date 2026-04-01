from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .config_loader import load_defaults
from .config_schema import CompanionDefaults

PROFILE_CONFIG_KEY = "companion_setting.config_json"
SESSION_OVERRIDE_KEY = "companion_runtime.session_override_json"
PENDING_NEXT_TURN_KEY = "companion_runtime.next_turn_json"
DEFAULTS = load_defaults()
DEFAULTS_PAYLOAD = DEFAULTS.model_dump(mode="json", exclude_none=True)


def normalize_config_patch(patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise ValueError("E_COMPANION_CONFIG_PATCH_INVALID")
    normalized: dict[str, Any] = {}
    for section, value in patch.items():
        section_name = str(section or "").strip()
        if section_name not in {"mode", "memory", "voice"}:
            raise ValueError("E_COMPANION_CONFIG_SECTION_INVALID")
        if not isinstance(value, dict):
            raise ValueError(f"E_COMPANION_CONFIG_SECTION_VALUE_INVALID: {section_name}")
        normalized[section_name] = json.loads(json.dumps(value))
    return normalized


def resolve_preview_config(
    *,
    profile_defaults: dict[str, Any],
    session_override: dict[str, Any],
    pending_next_turn: dict[str, Any],
    include_pending_next_turn: bool,
) -> CompanionDefaults:
    merged = merge_nested(DEFAULTS_PAYLOAD, profile_defaults)
    merged = merge_nested(merged, session_override)
    if include_pending_next_turn:
        merged = merge_nested(merged, pending_next_turn)
    return validate_config_payload(merged)


def validate_config_payload(payload: dict[str, Any]) -> CompanionDefaults:
    try:
        return CompanionDefaults.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"E_COMPANION_CONFIG_VALIDATION_FAILED: {exc}") from exc


def merge_nested(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(base))
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_nested(merged[key], value)
        else:
            merged[key] = json.loads(json.dumps(value))
    return merged


def decode_json_object(value: str) -> dict[str, Any]:
    raw = str(value or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def encode_json_object(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
