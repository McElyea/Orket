from __future__ import annotations

import asyncio
import os
from typing import Any, Callable, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel


class RuntimePolicyUpdateRequest(BaseModel):
    architecture_mode: Optional[str] = None
    frontend_framework_mode: Optional[str] = None
    project_surface_profile: Optional[str] = None
    small_project_builder_variant: Optional[str] = None
    state_backend_mode: Optional[str] = None
    run_ledger_mode: Optional[str] = None
    protocol_timezone: Optional[str] = None
    protocol_locale: Optional[str] = None
    protocol_network_mode: Optional[str] = None
    protocol_network_allowlist: Optional[str] = None
    protocol_env_allowlist: Optional[str] = None
    local_prompting_mode: Optional[str] = None
    local_prompting_allow_fallback: Optional[bool] = None
    local_prompting_fallback_profile_id: Optional[str] = None
    gitea_state_pilot_enabled: Optional[bool] = None


def build_settings_router(
    *,
    settings_order: tuple[str, ...],
    settings_schema: dict[str, dict[str, Any]],
    runtime_policy_options: Callable[[], dict[str, Any]],
    load_user_settings: Callable[[], dict[str, Any]],
    save_user_settings: Callable[[dict[str, Any]], None],
    runtime_policy_process_rules: Callable[[], dict[str, Any]],
    resolve_settings_snapshot: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    parse_setting_value: Callable[[str, Any], Any | None],
    settings_validation_error: Callable[[list[dict[str, Any]]], HTTPException],
    is_microservices_unlocked: Callable[[], bool],
    resolve_architecture_mode: Callable[[Any, Any, Any], str],
    resolve_frontend_framework_mode: Callable[[Any, Any, Any], str],
    resolve_project_surface_profile: Callable[[Any, Any, Any], str],
    resolve_small_project_builder_variant: Callable[[Any, Any, Any], str],
    resolve_state_backend_mode: Callable[[Any, Any, Any], str],
    resolve_run_ledger_mode: Callable[[Any, Any, Any], str],
    resolve_protocol_timezone_setting: Callable[[Any, Any, Any], str],
    resolve_protocol_locale_setting: Callable[[Any, Any, Any], str],
    resolve_protocol_network_mode_setting: Callable[[Any, Any, Any], str],
    resolve_protocol_network_allowlist_setting: Callable[[Any, Any, Any], str],
    resolve_protocol_env_allowlist_setting: Callable[[Any, Any, Any], str],
    resolve_local_prompting_mode: Callable[[Any, Any, Any], str],
    resolve_local_prompting_allow_fallback: Callable[[Any, Any, Any], bool],
    resolve_local_prompting_fallback_profile_id: Callable[[Any, Any, Any], str],
    resolve_gitea_state_pilot_enabled: Callable[[Any, Any, Any], bool],
    allowed_architecture_patterns: Callable[[], list[str]],
    is_microservices_pilot_stable: Callable[[], bool],
) -> APIRouter:
    router = APIRouter()

    @router.get("/system/runtime-policy/options")
    async def get_runtime_policy_options():
        return runtime_policy_options()

    @router.get("/settings")
    async def get_settings():
        user_settings = await asyncio.to_thread(load_user_settings)
        process_rules = runtime_policy_process_rules()
        return {"settings": resolve_settings_snapshot(user_settings, process_rules)}

    @router.patch("/settings")
    async def update_settings(payload: dict[str, Any] = Body(...)):
        editable = {key: payload[key] for key in settings_order if key in payload}
        errors: list[dict[str, Any]] = []
        for key in payload.keys():
            if key not in settings_schema:
                errors.append(
                    {
                        "field": key,
                        "code": "unknown_setting",
                        "message": "Setting is not user-editable.",
                    }
                )
        if not editable and not errors:
            raise HTTPException(status_code=400, detail="No editable settings provided.")

        options = runtime_policy_options()
        normalized: dict[str, Any] = {}
        for field, raw_value in editable.items():
            parsed = parse_setting_value(field, raw_value)
            if parsed is None:
                errors.append(
                    {
                        "field": field,
                        "code": "invalid_value",
                        "provided": raw_value,
                        "allowed_values": [
                            item.get("value") for item in options[field].get("options", []) if isinstance(item, dict)
                        ],
                    }
                )
                continue
            if field == "architecture_mode" and parsed == "force_microservices" and not is_microservices_unlocked():
                errors.append(
                    {
                        "field": field,
                        "code": "policy_guard",
                        "message": "force_microservices is locked until microservices readiness gates are satisfied.",
                    }
                )
                continue
            normalized[field] = parsed

        user_settings = (await asyncio.to_thread(load_user_settings)).copy()
        process_rules = runtime_policy_process_rules()
        candidate = user_settings.copy()
        candidate.update(normalized)
        snapshot = resolve_settings_snapshot(candidate, process_rules)
        if snapshot["state_backend_mode"]["value"] == "gitea" and not snapshot["gitea_state_pilot_enabled"]["value"]:
            errors.append(
                {
                    "field": "state_backend_mode",
                    "code": "policy_guard",
                    "message": "state_backend_mode='gitea' requires gitea_state_pilot_enabled=true.",
                }
            )

        if errors:
            raise settings_validation_error(errors)

        user_settings.update(normalized)
        await asyncio.to_thread(save_user_settings, user_settings)
        return {
            "ok": True,
            "saved": normalized,
            "settings": resolve_settings_snapshot(user_settings, process_rules),
        }

    @router.get("/system/runtime-policy")
    async def get_runtime_policy():
        user_settings = await asyncio.to_thread(load_user_settings)
        process_rules = runtime_policy_process_rules()

        architecture_mode = resolve_architecture_mode(
            os.environ.get("ORKET_ARCHITECTURE_MODE", ""),
            process_rules.get("architecture_mode"),
            user_settings.get("architecture_mode"),
        )
        frontend_framework_mode = resolve_frontend_framework_mode(
            os.environ.get("ORKET_FRONTEND_FRAMEWORK_MODE", ""),
            process_rules.get("frontend_framework_mode"),
            user_settings.get("frontend_framework_mode"),
        )
        project_surface_profile = resolve_project_surface_profile(
            os.environ.get("ORKET_PROJECT_SURFACE_PROFILE", ""),
            process_rules.get("project_surface_profile"),
            user_settings.get("project_surface_profile"),
        )
        small_project_builder_variant = resolve_small_project_builder_variant(
            os.environ.get("ORKET_SMALL_PROJECT_BUILDER_VARIANT", ""),
            process_rules.get("small_project_builder_variant"),
            user_settings.get("small_project_builder_variant"),
        )
        state_backend_mode = resolve_state_backend_mode(
            os.environ.get("ORKET_STATE_BACKEND_MODE", ""),
            process_rules.get("state_backend_mode"),
            user_settings.get("state_backend_mode"),
        )
        run_ledger_mode = resolve_run_ledger_mode(
            os.environ.get("ORKET_RUN_LEDGER_MODE", ""),
            process_rules.get("run_ledger_mode"),
            user_settings.get("run_ledger_mode"),
        )
        protocol_timezone = resolve_protocol_timezone_setting(
            os.environ.get("ORKET_PROTOCOL_TIMEZONE", ""),
            process_rules.get("protocol_timezone"),
            user_settings.get("protocol_timezone"),
        )
        protocol_locale = resolve_protocol_locale_setting(
            os.environ.get("ORKET_PROTOCOL_LOCALE", ""),
            process_rules.get("protocol_locale"),
            user_settings.get("protocol_locale"),
        )
        protocol_network_mode = resolve_protocol_network_mode_setting(
            os.environ.get("ORKET_PROTOCOL_NETWORK_MODE", ""),
            process_rules.get("protocol_network_mode"),
            user_settings.get("protocol_network_mode"),
        )
        protocol_network_allowlist = resolve_protocol_network_allowlist_setting(
            os.environ.get("ORKET_PROTOCOL_NETWORK_ALLOWLIST", ""),
            process_rules.get("protocol_network_allowlist"),
            user_settings.get("protocol_network_allowlist"),
        )
        protocol_env_allowlist = resolve_protocol_env_allowlist_setting(
            os.environ.get("ORKET_PROTOCOL_ENV_ALLOWLIST", ""),
            process_rules.get("protocol_env_allowlist"),
            user_settings.get("protocol_env_allowlist"),
        )
        local_prompting_mode = resolve_local_prompting_mode(
            os.environ.get("ORKET_LOCAL_PROMPTING_MODE", ""),
            process_rules.get("local_prompting_mode"),
            user_settings.get("local_prompting_mode"),
        )
        local_prompting_allow_fallback = resolve_local_prompting_allow_fallback(
            os.environ.get("ORKET_LOCAL_PROMPTING_ALLOW_FALLBACK", ""),
            process_rules.get("local_prompting_allow_fallback"),
            user_settings.get("local_prompting_allow_fallback"),
        )
        local_prompting_fallback_profile_id = resolve_local_prompting_fallback_profile_id(
            os.environ.get("ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID", ""),
            process_rules.get("local_prompting_fallback_profile_id"),
            user_settings.get("local_prompting_fallback_profile_id"),
        )
        gitea_state_pilot_enabled = resolve_gitea_state_pilot_enabled(
            os.environ.get("ORKET_ENABLE_GITEA_STATE_PILOT", ""),
            process_rules.get("gitea_state_pilot_enabled"),
            user_settings.get("gitea_state_pilot_enabled"),
        )
        return {
            "architecture_mode": architecture_mode,
            "frontend_framework_mode": frontend_framework_mode,
            "project_surface_profile": project_surface_profile,
            "small_project_builder_variant": small_project_builder_variant,
            "state_backend_mode": state_backend_mode,
            "run_ledger_mode": run_ledger_mode,
            "protocol_timezone": protocol_timezone,
            "protocol_locale": protocol_locale,
            "protocol_network_mode": protocol_network_mode,
            "protocol_network_allowlist": protocol_network_allowlist,
            "protocol_env_allowlist": protocol_env_allowlist,
            "local_prompting_mode": local_prompting_mode,
            "local_prompting_allow_fallback": local_prompting_allow_fallback,
            "local_prompting_fallback_profile_id": local_prompting_fallback_profile_id,
            "gitea_state_pilot_enabled": gitea_state_pilot_enabled,
            "default_architecture_mode": "force_monolith",
            "allowed_architecture_patterns": allowed_architecture_patterns(),
            "microservices_unlocked": is_microservices_unlocked(),
            "microservices_pilot_stable": is_microservices_pilot_stable(),
        }

    @router.post("/system/runtime-policy")
    async def update_runtime_policy(req: RuntimePolicyUpdateRequest):
        current = (await asyncio.to_thread(load_user_settings)).copy()
        if req.architecture_mode is not None:
            current["architecture_mode"] = resolve_architecture_mode(req.architecture_mode, None, None)
        if req.frontend_framework_mode is not None:
            current["frontend_framework_mode"] = resolve_frontend_framework_mode(
                req.frontend_framework_mode,
                None,
                None,
            )
        if req.project_surface_profile is not None:
            current["project_surface_profile"] = resolve_project_surface_profile(
                req.project_surface_profile,
                None,
                None,
            )
        if req.small_project_builder_variant is not None:
            current["small_project_builder_variant"] = resolve_small_project_builder_variant(
                req.small_project_builder_variant,
                None,
                None,
            )
        if req.state_backend_mode is not None:
            current["state_backend_mode"] = resolve_state_backend_mode(req.state_backend_mode, None, None)
        if req.run_ledger_mode is not None:
            current["run_ledger_mode"] = resolve_run_ledger_mode(req.run_ledger_mode, None, None)
        if req.protocol_timezone is not None:
            current["protocol_timezone"] = resolve_protocol_timezone_setting(req.protocol_timezone, None, None)
        if req.protocol_locale is not None:
            current["protocol_locale"] = resolve_protocol_locale_setting(req.protocol_locale, None, None)
        if req.protocol_network_mode is not None:
            current["protocol_network_mode"] = resolve_protocol_network_mode_setting(
                req.protocol_network_mode,
                None,
                None,
            )
        if req.protocol_network_allowlist is not None:
            current["protocol_network_allowlist"] = resolve_protocol_network_allowlist_setting(
                req.protocol_network_allowlist,
                None,
                None,
            )
        if req.protocol_env_allowlist is not None:
            current["protocol_env_allowlist"] = resolve_protocol_env_allowlist_setting(
                req.protocol_env_allowlist,
                None,
                None,
            )
        if req.local_prompting_mode is not None:
            current["local_prompting_mode"] = resolve_local_prompting_mode(req.local_prompting_mode, None, None)
        if req.local_prompting_allow_fallback is not None:
            current["local_prompting_allow_fallback"] = bool(
                resolve_local_prompting_allow_fallback(req.local_prompting_allow_fallback, None, None)
            )
        if req.local_prompting_fallback_profile_id is not None:
            current["local_prompting_fallback_profile_id"] = resolve_local_prompting_fallback_profile_id(
                req.local_prompting_fallback_profile_id,
                None,
                None,
            )
        if req.gitea_state_pilot_enabled is not None:
            current["gitea_state_pilot_enabled"] = bool(
                resolve_gitea_state_pilot_enabled(req.gitea_state_pilot_enabled, None, None)
            )
        await asyncio.to_thread(save_user_settings, current)
        return {
            "ok": True,
            "saved": {
                "architecture_mode": current.get("architecture_mode"),
                "frontend_framework_mode": current.get("frontend_framework_mode"),
                "project_surface_profile": current.get("project_surface_profile"),
                "small_project_builder_variant": current.get("small_project_builder_variant"),
                "state_backend_mode": current.get("state_backend_mode"),
                "run_ledger_mode": current.get("run_ledger_mode"),
                "protocol_timezone": current.get("protocol_timezone"),
                "protocol_locale": current.get("protocol_locale"),
                "protocol_network_mode": current.get("protocol_network_mode"),
                "protocol_network_allowlist": current.get("protocol_network_allowlist"),
                "protocol_env_allowlist": current.get("protocol_env_allowlist"),
                "local_prompting_mode": current.get("local_prompting_mode"),
                "local_prompting_allow_fallback": current.get("local_prompting_allow_fallback"),
                "local_prompting_fallback_profile_id": current.get("local_prompting_fallback_profile_id"),
                "gitea_state_pilot_enabled": current.get("gitea_state_pilot_enabled"),
            },
        }

    return router
