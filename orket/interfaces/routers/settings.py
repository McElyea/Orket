from __future__ import annotations

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
        user_settings = load_user_settings()
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
                        "allowed_values": [item.get("value") for item in options[field].get("options", []) if isinstance(item, dict)],
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

        user_settings = load_user_settings().copy()
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
        save_user_settings(user_settings)
        return {
            "ok": True,
            "saved": normalized,
            "settings": resolve_settings_snapshot(user_settings, process_rules),
        }

    @router.get("/system/runtime-policy")
    async def get_runtime_policy():
        user_settings = load_user_settings()
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
            "gitea_state_pilot_enabled": gitea_state_pilot_enabled,
            "default_architecture_mode": "force_monolith",
            "allowed_architecture_patterns": allowed_architecture_patterns(),
            "microservices_unlocked": is_microservices_unlocked(),
            "microservices_pilot_stable": is_microservices_pilot_stable(),
        }

    @router.post("/system/runtime-policy")
    async def update_runtime_policy(req: RuntimePolicyUpdateRequest):
        current = load_user_settings().copy()
        if req.architecture_mode is not None:
            current["architecture_mode"] = resolve_architecture_mode(req.architecture_mode, None, None)
        if req.frontend_framework_mode is not None:
            current["frontend_framework_mode"] = resolve_frontend_framework_mode(req.frontend_framework_mode, None, None)
        if req.project_surface_profile is not None:
            current["project_surface_profile"] = resolve_project_surface_profile(req.project_surface_profile, None, None)
        if req.small_project_builder_variant is not None:
            current["small_project_builder_variant"] = resolve_small_project_builder_variant(
                req.small_project_builder_variant,
                None,
                None,
            )
        if req.state_backend_mode is not None:
            current["state_backend_mode"] = resolve_state_backend_mode(req.state_backend_mode, None, None)
        if req.gitea_state_pilot_enabled is not None:
            current["gitea_state_pilot_enabled"] = bool(
                resolve_gitea_state_pilot_enabled(req.gitea_state_pilot_enabled, None, None)
            )
        save_user_settings(current)
        return {
            "ok": True,
            "saved": {
                "architecture_mode": current.get("architecture_mode"),
                "frontend_framework_mode": current.get("frontend_framework_mode"),
                "project_surface_profile": current.get("project_surface_profile"),
                "small_project_builder_variant": current.get("small_project_builder_variant"),
                "state_backend_mode": current.get("state_backend_mode"),
                "gitea_state_pilot_enabled": current.get("gitea_state_pilot_enabled"),
            },
        }

    return router

