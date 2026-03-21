from __future__ import annotations

import os
from typing import Any

from orket.settings import load_user_settings

_TRUTHY = {"1", "true", "yes", "on", "enabled"}
_FALSY = {"0", "false", "no", "off", "disabled"}


def resolve_str(
    *env_names: str,
    process_rules: dict[str, Any] | None = None,
    process_key: str = "",
    user_key: str = "",
    user_settings: dict[str, Any] | None = None,
    default: str = "",
) -> str:
    for name in env_names:
        value = str(os.getenv(name, "")).strip()
        if value:
            return value
    if process_rules and process_key:
        value = str(process_rules.get(process_key, "")).strip()
        if value:
            return value
    if user_key:
        source = user_settings if isinstance(user_settings, dict) else load_user_settings()
        value = str(source.get(user_key, "")).strip()
        if value:
            return value
    return default


def resolve_bool(
    *env_names: str,
    process_rules: dict[str, Any] | None = None,
    process_key: str = "",
    user_key: str = "",
    user_settings: dict[str, Any] | None = None,
    default: bool = False,
) -> bool:
    raw = resolve_str(
        *env_names,
        process_rules=process_rules,
        process_key=process_key,
        user_key=user_key,
        user_settings=user_settings,
    ).lower()
    if raw in _TRUTHY:
        return True
    if raw in _FALSY:
        return False
    return default
