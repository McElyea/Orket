from __future__ import annotations

from typing import Any

from orket.application.services.runtime_policy import (
    resolve_local_prompting_allow_fallback,
    resolve_local_prompting_fallback_profile_id,
    resolve_local_prompting_mode,
)
from orket.runtime.config import settings


def select_local_prompting_mode(*, user_settings: dict[str, Any], process_rules: dict[str, Any]) -> str:
    return str(
        resolve_local_prompting_mode(
            settings.resolve_str(
                "ORKET_LOCAL_PROMPTING_MODE",
                process_rules=process_rules,
                process_key="local_prompting_mode",
                user_key="local_prompting_mode",
                user_settings=user_settings,
            ),
            "",
            "",
        )
    )


def select_local_prompting_allow_fallback(*, user_settings: dict[str, Any], process_rules: dict[str, Any]) -> bool:
    return bool(
        resolve_local_prompting_allow_fallback(
            settings.resolve_str(
                "ORKET_LOCAL_PROMPTING_ALLOW_FALLBACK",
                process_rules=process_rules,
                process_key="local_prompting_allow_fallback",
                user_key="local_prompting_allow_fallback",
                user_settings=user_settings,
            ),
            "",
            "",
        )
    )


def select_local_prompting_fallback_profile_id(*, user_settings: dict[str, Any], process_rules: dict[str, Any]) -> str:
    return str(
        resolve_local_prompting_fallback_profile_id(
            settings.resolve_str(
                "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID",
                process_rules=process_rules,
                process_key="local_prompting_fallback_profile_id",
                user_key="local_prompting_fallback_profile_id",
                user_settings=user_settings,
            ),
            "",
            "",
        )
    )


def select_prompt_resolver_mode(*, process_rules: dict[str, Any]) -> str:
    value = settings.resolve_str(
        "ORKET_PROMPT_RESOLVER_MODE", process_rules=process_rules, process_key="prompt_resolver_mode"
    ).lower()
    if value in {"resolver", "compiler"}:
        return value
    return "compiler"


def select_prompt_selection_policy(*, process_rules: dict[str, Any]) -> str:
    value = settings.resolve_str(
        "ORKET_PROMPT_SELECTION_POLICY", process_rules=process_rules, process_key="prompt_selection_policy"
    ).lower()
    if value in {"stable", "canary", "exact"}:
        return value
    return "stable"


def select_prompt_selection_strict(*, process_rules: dict[str, Any]) -> bool:
    return bool(
        settings.resolve_bool(
            "ORKET_PROMPT_SELECTION_STRICT",
            process_rules=process_rules,
            process_key="prompt_selection_strict",
            default=True,
        )
    )


def select_prompt_version_exact(*, process_rules: dict[str, Any]) -> str:
    return str(
        settings.resolve_str("ORKET_PROMPT_VERSION_EXACT", process_rules=process_rules, process_key="prompt_version_exact")
    )


def select_prompt_patch(*, process_rules: dict[str, Any]) -> str:
    return str(settings.resolve_str("ORKET_PROMPT_PATCH", process_rules=process_rules, process_key="prompt_patch"))


def select_prompt_patch_label(*, process_rules: dict[str, Any]) -> str:
    return str(settings.resolve_str("ORKET_PROMPT_PATCH_LABEL", process_rules=process_rules, process_key="prompt_patch_label"))
