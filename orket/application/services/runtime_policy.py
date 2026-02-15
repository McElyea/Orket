from __future__ import annotations

import json
import os
from pathlib import Path
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
DEFAULT_STATE_BACKEND_MODE = "local"
DEFAULT_MICROSERVICES_UNLOCK_REPORT = "benchmarks/results/microservices_unlock_check.json"
DEFAULT_MICROSERVICES_PILOT_STABILITY_REPORT = "benchmarks/results/microservices_pilot_stability_check.json"

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
STATE_BACKEND_MODE_OPTIONS: List[Dict[str, str]] = [
    {"value": "local", "label": "Local DB (Default)"},
    {"value": "gitea", "label": "Gitea (Experimental)"},
]


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _pick_first_non_empty(values: Iterable[Any]) -> str:
    for value in values:
        normalized = _normalize(value)
        if normalized:
            return normalized
    return ""


def _read_unlock_report(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _env_bool(name: str) -> bool | None:
    raw = (os.environ.get(name) or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return None


def is_microservices_unlocked() -> bool:
    env_override = _env_bool("ORKET_ENABLE_MICROSERVICES")
    if env_override is not None:
        return bool(env_override)
    report_path = Path(
        str(os.environ.get("ORKET_MICROSERVICES_UNLOCK_REPORT") or DEFAULT_MICROSERVICES_UNLOCK_REPORT)
    )
    report = _read_unlock_report(report_path)
    return bool(report.get("unlocked"))


def is_microservices_pilot_stable() -> bool:
    report_path = Path(
        str(
            os.environ.get("ORKET_MICROSERVICES_PILOT_STABILITY_REPORT")
            or DEFAULT_MICROSERVICES_PILOT_STABILITY_REPORT
        )
    )
    report = _read_unlock_report(report_path)
    return bool(report.get("stable"))


def allowed_architecture_patterns() -> List[str]:
    if is_microservices_unlocked():
        return ["monolith", "microservices"]
    return ["monolith"]


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
    resolved = aliases.get(raw, DEFAULT_ARCHITECTURE_MODE)
    if resolved == "force_microservices" and not is_microservices_unlocked():
        return DEFAULT_ARCHITECTURE_MODE
    return resolved


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
    microservices_unlocked = is_microservices_unlocked()
    microservices_pilot_stable = is_microservices_pilot_stable()
    if microservices_unlocked:
        architecture_mode_options = ARCHITECTURE_MODE_OPTIONS
    else:
        architecture_mode_options = [
            {"value": "force_monolith", "label": "Monolith (Forced)"},
            {"value": "architect_decides", "label": "Architect Decides (Monolith Only While Locked)"},
        ]
    return {
        "architecture_mode": {
            "default": DEFAULT_ARCHITECTURE_MODE,
            "options": architecture_mode_options,
            "input_style": "radio",
            "microservices_unlocked": microservices_unlocked,
            "microservices_pilot_stable": microservices_pilot_stable,
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
        "state_backend_mode": {
            "default": DEFAULT_STATE_BACKEND_MODE,
            "options": STATE_BACKEND_MODE_OPTIONS,
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


def resolve_state_backend_mode(*values: Any) -> str:
    raw = _pick_first_non_empty(values)
    aliases = {
        "local": "local",
        "sqlite": "local",
        "db": "local",
        "gitea": "gitea",
    }
    return aliases.get(raw, DEFAULT_STATE_BACKEND_MODE)
