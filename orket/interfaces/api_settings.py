"""Pure API settings representation over captured runtime policy inputs."""
from __future__ import annotations

from typing import Any

from orket.application.services.runtime_policy import (
    is_microservices_unlocked,
    resolve_architecture_mode,
    resolve_frontend_framework_mode,
    resolve_gitea_state_pilot_enabled,
    resolve_local_prompting_allow_fallback,
    resolve_local_prompting_fallback_profile_id,
    resolve_local_prompting_mode,
    resolve_project_surface_profile,
    resolve_protocol_env_allowlist_setting,
    resolve_protocol_locale_setting,
    resolve_protocol_network_allowlist_setting,
    resolve_protocol_network_mode_setting,
    resolve_protocol_timezone_setting,
    resolve_run_ledger_mode,
    resolve_small_project_builder_variant,
    resolve_state_backend_mode,
    runtime_policy_options,
)
from orket.application.services.runtime_policy_inputs import ArchitecturePolicySnapshot, RuntimePolicySnapshot

SETTINGS_SCHEMA: dict[str, dict[str, Any]] = {
    "architecture_mode": {
        "env_var": "ORKET_ARCHITECTURE_MODE",
        "aliases": {
            "force_monolith": "force_monolith",
            "monolith": "force_monolith",
            "force_microservices": "force_microservices",
            "microservices": "force_microservices",
            "architect_decides": "architect_decides",
            "architect_decide": "architect_decides",
            "let_architect_decide": "architect_decides",
        },
        "type": "string",
    },
    "frontend_framework_mode": {
        "env_var": "ORKET_FRONTEND_FRAMEWORK_MODE",
        "aliases": {
            "force_vue": "force_vue",
            "vue": "force_vue",
            "force_react": "force_react",
            "react": "force_react",
            "force_angular": "force_angular",
            "angular": "force_angular",
            "architect_decides": "architect_decides",
            "let_architect_decide": "architect_decides",
        },
        "type": "string",
    },
    "project_surface_profile": {
        "env_var": "ORKET_PROJECT_SURFACE_PROFILE",
        "aliases": {
            "unspecified": "unspecified",
            "legacy": "unspecified",
            "backend_only": "backend_only",
            "backend": "backend_only",
            "api_only": "backend_only",
            "cli": "cli",
            "api_vue": "api_vue",
            "api+vue": "api_vue",
            "vue_api": "api_vue",
            "tui": "tui",
        },
        "type": "string",
    },
    "small_project_builder_variant": {
        "env_var": "ORKET_SMALL_PROJECT_BUILDER_VARIANT",
        "aliases": {
            "auto": "auto",
            "coder": "coder",
            "architect": "architect",
        },
        "type": "string",
    },
    "state_backend_mode": {
        "env_var": "ORKET_STATE_BACKEND_MODE",
        "aliases": {
            "local": "local",
            "sqlite": "local",
            "db": "local",
            "gitea": "gitea",
        },
        "type": "string",
    },
    "run_ledger_mode": {
        "env_var": "ORKET_RUN_LEDGER_MODE",
        "aliases": {
            "sqlite": "sqlite",
            "compat": "sqlite",
            "protocol": "protocol",
            "append_only": "protocol",
            "dual_write": "dual_write",
            "dual": "dual_write",
        },
        "type": "string",
    },
    "protocol_timezone": {
        "env_var": "ORKET_PROTOCOL_TIMEZONE",
        "type": "string_freeform",
    },
    "protocol_locale": {
        "env_var": "ORKET_PROTOCOL_LOCALE",
        "type": "string_freeform",
    },
    "protocol_network_mode": {
        "env_var": "ORKET_PROTOCOL_NETWORK_MODE",
        "aliases": {
            "off": "off",
            "offline": "off",
            "disabled": "off",
            "allowlist": "allowlist",
            "allow_list": "allowlist",
        },
        "type": "string",
    },
    "protocol_network_allowlist": {
        "env_var": "ORKET_PROTOCOL_NETWORK_ALLOWLIST",
        "type": "string_freeform",
    },
    "protocol_env_allowlist": {
        "env_var": "ORKET_PROTOCOL_ENV_ALLOWLIST",
        "type": "string_freeform",
    },
    "local_prompting_mode": {
        "env_var": "ORKET_LOCAL_PROMPTING_MODE",
        "aliases": {
            "shadow": "shadow",
            "compat": "compat",
            "enforce": "enforce",
        },
        "type": "string",
    },
    "local_prompting_allow_fallback": {
        "env_var": "ORKET_LOCAL_PROMPTING_ALLOW_FALLBACK",
        "type": "boolean",
    },
    "local_prompting_fallback_profile_id": {
        "env_var": "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID",
        "type": "string_freeform",
    },
    "gitea_state_pilot_enabled": {
        "env_var": "ORKET_ENABLE_GITEA_STATE_PILOT",
        "type": "boolean",
    },
}

SETTINGS_ORDER = tuple(SETTINGS_SCHEMA.keys())


def _normalize_setting_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def parse_setting_value(field: str, value: Any) -> Any | None:
    schema = SETTINGS_SCHEMA[field]
    if schema["type"] == "boolean":
        if isinstance(value, bool):
            return value
        token = _normalize_setting_token(value)
        if token in {"1", "true", "yes", "on", "enabled"}:
            return True
        if token in {"0", "false", "no", "off", "disabled"}:
            return False
        return None
    if schema["type"] == "string_freeform":
        parsed = str(value or "").strip()
        return parsed if parsed else None
    token = _normalize_setting_token(value)
    aliases = schema.get("aliases", {})
    return aliases.get(token)


def _resolve_runtime_setting_value(field: str, env_value: Any, process_value: Any, user_value: Any,
                                   *, policy: ArchitecturePolicySnapshot) -> Any:
    if field == "architecture_mode":
        return resolve_architecture_mode(env_value, process_value, user_value, policy=policy)
    if field == "frontend_framework_mode":
        return resolve_frontend_framework_mode(env_value, process_value, user_value)
    if field == "project_surface_profile":
        return resolve_project_surface_profile(env_value, process_value, user_value)
    if field == "small_project_builder_variant":
        return resolve_small_project_builder_variant(env_value, process_value, user_value)
    if field == "state_backend_mode":
        return resolve_state_backend_mode(env_value, process_value, user_value)
    if field == "run_ledger_mode":
        return resolve_run_ledger_mode(env_value, process_value, user_value)
    if field == "protocol_timezone":
        return resolve_protocol_timezone_setting(env_value, process_value, user_value)
    if field == "protocol_locale":
        return resolve_protocol_locale_setting(env_value, process_value, user_value)
    if field == "protocol_network_mode":
        return resolve_protocol_network_mode_setting(env_value, process_value, user_value)
    if field == "protocol_network_allowlist":
        return resolve_protocol_network_allowlist_setting(env_value, process_value, user_value)
    if field == "protocol_env_allowlist":
        return resolve_protocol_env_allowlist_setting(env_value, process_value, user_value)
    if field == "local_prompting_mode":
        return resolve_local_prompting_mode(env_value, process_value, user_value)
    if field == "local_prompting_allow_fallback":
        return bool(resolve_local_prompting_allow_fallback(env_value, process_value, user_value))
    if field == "local_prompting_fallback_profile_id":
        return resolve_local_prompting_fallback_profile_id(env_value, process_value, user_value)
    if field == "gitea_state_pilot_enabled":
        return bool(resolve_gitea_state_pilot_enabled(env_value, process_value, user_value))
    raise KeyError(f"Unsupported runtime setting '{field}'")


def resolve_settings_snapshot(user_settings: dict[str, Any], process_rules: dict[str, Any],
                               policy: RuntimePolicySnapshot) -> dict[str, Any]:
    options = runtime_policy_options(policy)
    snapshot: dict[str, Any] = {}
    microservices_unlocked = is_microservices_unlocked(policy.architecture)
    for field in SETTINGS_ORDER:
        schema = SETTINGS_SCHEMA[field]
        env_value = policy.environment.get(schema["env_var"], "")
        process_value = process_rules.get(field)
        user_value = user_settings.get(field)
        effective = _resolve_runtime_setting_value(field, env_value, process_value, user_value, policy=policy.architecture)

        source = "default"
        # Keep state backend settings stable across machines with ambient env vars.
        # API settings UX should primarily reflect explicit policy/user choices.
        if (
            field not in {"state_backend_mode", "run_ledger_mode"}
            and parse_setting_value(field, env_value) is not None
        ):
            source = "env"
        elif parse_setting_value(field, process_value) is not None:
            source = "process_rules"
        elif parse_setting_value(field, user_value) is not None:
            source = "user"

        metadata = options[field]
        entry = {
            "value": effective,
            "source": source,
            "default": metadata.get("default"),
            "type": schema["type"],
            "input_style": metadata.get("input_style"),
            "allowed_values": [item.get("value") for item in metadata.get("options", []) if isinstance(item, dict)],
        }
        if field == "architecture_mode":
            requested = parse_setting_value(field, env_value)
            if requested is None:
                requested = parse_setting_value(field, process_value)
            if requested is None:
                requested = parse_setting_value(field, user_value)
            if requested == "force_microservices" and not microservices_unlocked:
                entry["policy_guard"] = "microservices_locked"
        snapshot[field] = entry
    return snapshot
