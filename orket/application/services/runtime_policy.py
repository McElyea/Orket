from __future__ import annotations

from typing import Any, Dict, Iterable, List


ARCHITECTURE_MODE_OPTIONS: List[Dict[str, str]] = [
    {"value": "force_monolith", "label": "Monolith (Forced)"},
    {"value": "force_microservices", "label": "Microservices (Forced)"},
    {"value": "architect_decides", "label": "Architect Decides"},
]

FRONTEND_FRAMEWORK_MODE_OPTIONS: List[Dict[str, str]] = [
    {"value": "force_vue", "label": "Vue (Forced)"},
    {"value": "force_react", "label": "React (Forced)"},
    {"value": "force_angular", "label": "Angular (Forced)"},
    {"value": "architect_decides", "label": "Architect Decides"},
]

DEFAULT_ARCHITECTURE_MODE = "force_monolith"
DEFAULT_FRONTEND_FRAMEWORK_MODE = "force_vue"
DEFAULT_PROJECT_SURFACE_PROFILE = "unspecified"
DEFAULT_SMALL_PROJECT_BUILDER_VARIANT = "auto"

PROJECT_SURFACE_PROFILE_OPTIONS: List[Dict[str, str]] = [
    {"value": "unspecified", "label": "Unspecified (Legacy Defaults)"},
    {"value": "backend_only", "label": "Backend Only"},
    {"value": "cli", "label": "CLI App"},
    {"value": "api_vue", "label": "API + Vue Frontend"},
    {"value": "tui", "label": "TUI App"},
]
SMALL_PROJECT_BUILDER_VARIANT_OPTIONS: List[Dict[str, str]] = [
    {"value": "auto", "label": "Auto"},
    {"value": "coder", "label": "Coder Builder"},
    {"value": "architect", "label": "Architect Builder"},
]


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _pick_first_non_empty(values: Iterable[Any]) -> str:
    for value in values:
        normalized = _normalize(value)
        if normalized:
            return normalized
    return ""


def resolve_architecture_mode(*values: Any) -> str:
    raw = _pick_first_non_empty(values)
    aliases = {
        "force_monolith": "force_monolith",
        "monolith": "force_monolith",
        "force_microservices": "force_microservices",
        "microservices": "force_microservices",
        "architect_decides": "architect_decides",
        "architect_decide": "architect_decides",
        "let_architect_decide": "architect_decides",
    }
    return aliases.get(raw, DEFAULT_ARCHITECTURE_MODE)


def resolve_frontend_framework_mode(*values: Any) -> str:
    raw = _pick_first_non_empty(values)
    aliases = {
        "force_vue": "force_vue",
        "vue": "force_vue",
        "force_react": "force_react",
        "react": "force_react",
        "force_angular": "force_angular",
        "angular": "force_angular",
        "architect_decides": "architect_decides",
        "let_architect_decide": "architect_decides",
    }
    return aliases.get(raw, DEFAULT_FRONTEND_FRAMEWORK_MODE)


def runtime_policy_options() -> Dict[str, Any]:
    return {
        "architecture_mode": {
            "default": DEFAULT_ARCHITECTURE_MODE,
            "options": ARCHITECTURE_MODE_OPTIONS,
            "input_style": "radio",
        },
        "frontend_framework_mode": {
            "default": DEFAULT_FRONTEND_FRAMEWORK_MODE,
            "options": FRONTEND_FRAMEWORK_MODE_OPTIONS,
            "input_style": "radio",
        },
        "project_surface_profile": {
            "default": DEFAULT_PROJECT_SURFACE_PROFILE,
            "options": PROJECT_SURFACE_PROFILE_OPTIONS,
            "input_style": "radio",
        },
        "small_project_builder_variant": {
            "default": DEFAULT_SMALL_PROJECT_BUILDER_VARIANT,
            "options": SMALL_PROJECT_BUILDER_VARIANT_OPTIONS,
            "input_style": "radio",
        },
    }


def resolve_project_surface_profile(*values: Any) -> str:
    raw = _pick_first_non_empty(values)
    aliases = {
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
    }
    return aliases.get(raw, DEFAULT_PROJECT_SURFACE_PROFILE)


def resolve_small_project_builder_variant(*values: Any) -> str:
    raw = _pick_first_non_empty(values)
    aliases = {
        "auto": "auto",
        "coder": "coder",
        "architect": "architect",
    }
    return aliases.get(raw, DEFAULT_SMALL_PROJECT_BUILDER_VARIANT)
