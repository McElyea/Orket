from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orket.application.services.runtime_policy import (
    resolve_architecture_mode,
    resolve_frontend_framework_mode,
    resolve_project_surface_profile,
    resolve_small_project_builder_variant,
)
from orket.application.services.runtime_policy_inputs import ArchitecturePolicySnapshot
from orket.runtime.config import settings


def organization_process_rules(org: Any) -> dict[str, Any]:
    process_rules = getattr(org, "process_rules", None) if org else None
    return process_rules if isinstance(process_rules, dict) else {}


def select_architecture_mode(
    *,
    user_settings: dict[str, Any],
    process_rules: dict[str, Any],
    environment: Mapping[str, str],
    architecture_policy: ArchitecturePolicySnapshot,
) -> str:
    raw = settings.resolve_str(
        "ORKET_ARCHITECTURE_MODE",
        process_rules=process_rules,
        process_key="architecture_mode",
        user_key="architecture_mode",
        user_settings=user_settings,
        environment=environment,
    )
    return str(resolve_architecture_mode(raw, "", "", policy=architecture_policy))


def select_frontend_framework_mode(*, user_settings: dict[str, Any], process_rules: dict[str, Any]) -> str:
    raw = settings.resolve_str(
        "ORKET_FRONTEND_FRAMEWORK_MODE",
        process_rules=process_rules,
        process_key="frontend_framework_mode",
        user_key="frontend_framework_mode",
        user_settings=user_settings,
    )
    return str(resolve_frontend_framework_mode(raw, "", ""))


def select_architecture_pattern(mode: str) -> str | None:
    if mode == "force_microservices":
        return "microservices"
    if mode == "force_monolith":
        return "monolith"
    return None


def select_project_surface_profile(*, user_settings: dict[str, Any], process_rules: dict[str, Any]) -> str:
    raw = settings.resolve_str(
        "ORKET_PROJECT_SURFACE_PROFILE",
        process_rules=process_rules,
        process_key="project_surface_profile",
        user_key="project_surface_profile",
        user_settings=user_settings,
    )
    return str(resolve_project_surface_profile(raw, "", ""))


def select_small_project_builder_variant(*, user_settings: dict[str, Any], process_rules: dict[str, Any]) -> str:
    raw = settings.resolve_str(
        "ORKET_SMALL_PROJECT_BUILDER_VARIANT",
        process_rules=process_rules,
        process_key="small_project_builder_variant",
        user_key="small_project_builder_variant",
        user_settings=user_settings,
    )
    return str(resolve_small_project_builder_variant(raw, "", ""))


def select_workflow_profile(*, process_rules: dict[str, Any]) -> str:
    raw = settings.resolve_str("ORKET_WORKFLOW_PROFILE", process_rules=process_rules, process_key="workflow_profile").lower()
    if raw in {"legacy_cards_v1", "project_task_v1"}:
        return raw
    default_raw = settings.resolve_str(
        "ORKET_WORKFLOW_PROFILE_DEFAULT", process_rules=process_rules, process_key="workflow_profile_default"
    ).lower()
    if default_raw in {"legacy_cards_v1", "project_task_v1"}:
        return default_raw
    return "legacy_cards_v1"


def select_bool_flag(env_key: str, org_key: str, default: bool = False, *, process_rules: dict[str, Any]) -> bool:
    return bool(settings.resolve_bool(env_key, process_rules=process_rules, process_key=org_key, default=default))


def select_verification_scope_limits(*, org: Any) -> dict[str, int | None]:
    defaults: dict[str, int | None] = {
        "max_workspace_items": None,
        "max_active_context_items": None,
        "max_passive_context_items": None,
        "max_archived_context_items": None,
        "max_total_context_items": None,
    }
    if not (org and isinstance(getattr(org, "process_rules", None), dict)):
        return defaults
    raw = org.process_rules.get("verification_scope_limits")
    if not isinstance(raw, dict):
        return defaults
    resolved = dict(defaults)
    for key in list(defaults.keys()):
        value = raw.get(key)
        if value is None:
            continue
        try:
            resolved[key] = max(0, int(value))
        except (TypeError, ValueError):
            resolved[key] = None
    return resolved
