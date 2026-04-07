from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from orket.settings import load_user_settings

_TRUTHY = {"1", "true", "yes", "on", "enabled"}
_FALSY = {"0", "false", "no", "off", "disabled"}


def _process_rule_token(process_rules: Any, process_key: str) -> str:
    if not process_rules or not process_key:
        return ""
    if isinstance(process_rules, Mapping):
        value = process_rules.get(process_key, "")
    else:
        value = getattr(process_rules, process_key, "")
    return str(value if value is not None else "").strip()


def resolve_str(
    *env_names: str,
    process_rules: Any = None,
    process_key: str = "",
    user_key: str = "",
    user_settings: dict[str, Any] | None = None,
    default: str = "",
) -> str:
    for name in env_names:
        value = str(os.getenv(name, "")).strip()
        if value:
            return value
    value = _process_rule_token(process_rules, process_key)
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
    process_rules: Any = None,
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
