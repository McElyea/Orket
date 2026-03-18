from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

from orket.runtime.determinism_controls import (
    build_determinism_controls,
    resolve_clock_artifact_ref as resolve_protocol_clock_artifact_ref,
    resolve_clock_mode as resolve_protocol_clock_mode,
    resolve_env_allowlist as resolve_protocol_env_allowlist,
    resolve_locale as resolve_protocol_locale,
    resolve_network_allowlist as resolve_protocol_network_allowlist,
    resolve_network_mode as resolve_protocol_network_mode,
    resolve_timezone as resolve_protocol_timezone,
)


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
DEFAULT_RUN_LEDGER_MODE = "sqlite"
DEFAULT_GITEA_STATE_PILOT_ENABLED = False
DEFAULT_MICROSERVICES_UNLOCK_REPORT = "benchmarks/results/microservices_unlock_check.json"
DEFAULT_MICROSERVICES_PILOT_STABILITY_REPORT = "benchmarks/results/microservices_pilot_stability_check.json"
DEFAULT_GITEA_WORKER_MAX_ITERATIONS = 100
DEFAULT_GITEA_WORKER_MAX_IDLE_STREAK = 10
DEFAULT_GITEA_WORKER_MAX_DURATION_SECONDS = 60.0
DEFAULT_PROTOCOL_TIMEZONE = "UTC"
DEFAULT_PROTOCOL_LOCALE = "C.UTF-8"
DEFAULT_PROTOCOL_NETWORK_MODE = "off"
DEFAULT_PROTOCOL_NETWORK_ALLOWLIST = ""
DEFAULT_PROTOCOL_ENV_ALLOWLIST = ""
DEFAULT_LOCAL_PROMPTING_MODE = "shadow"
DEFAULT_LOCAL_PROMPTING_ALLOW_FALLBACK = False
DEFAULT_LOCAL_PROMPTING_FALLBACK_PROFILE_ID = ""

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
RUN_LEDGER_MODE_OPTIONS: List[Dict[str, str]] = [
    {"value": "sqlite", "label": "SQLite (Compat Default)"},
    {"value": "protocol", "label": "Protocol Append-Only"},
    {"value": "dual_write", "label": "Protocol Primary + SQLite Lifecycle Mirror"},
]
PROTOCOL_NETWORK_MODE_OPTIONS: List[Dict[str, str]] = [
    {"value": "off", "label": "Off (Deterministic Default)"},
    {"value": "allowlist", "label": "Allowlist"},
]
GITEA_STATE_PILOT_ENABLED_OPTIONS: List[Dict[str, str]] = [
    {"value": "enabled", "label": "Enabled"},
    {"value": "disabled", "label": "Disabled"},
]
LOCAL_PROMPTING_MODE_OPTIONS: List[Dict[str, str]] = [
    {"value": "shadow", "label": "Shadow"},
    {"value": "compat", "label": "Compat"},
    {"value": "enforce", "label": "Enforce"},
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
    report_path = Path(str(os.environ.get("ORKET_MICROSERVICES_UNLOCK_REPORT") or DEFAULT_MICROSERVICES_UNLOCK_REPORT))
    report = _read_unlock_report(report_path)
    return bool(report.get("unlocked"))


def is_microservices_pilot_stable() -> bool:
    report_path = Path(
        str(
            os.environ.get("ORKET_MICROSERVICES_PILOT_STABILITY_REPORT") or DEFAULT_MICROSERVICES_PILOT_STABILITY_REPORT
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

    def text_option(default):
        return {"default": default, "options": [], "input_style": "text"}

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
        "run_ledger_mode": {
            "default": DEFAULT_RUN_LEDGER_MODE,
            "options": RUN_LEDGER_MODE_OPTIONS,
            "input_style": "radio",
        },
        "protocol_timezone": text_option(DEFAULT_PROTOCOL_TIMEZONE),
        "protocol_locale": text_option(DEFAULT_PROTOCOL_LOCALE),
        "protocol_network_mode": {
            "default": DEFAULT_PROTOCOL_NETWORK_MODE,
            "options": PROTOCOL_NETWORK_MODE_OPTIONS,
            "input_style": "radio",
        },
        "protocol_network_allowlist": text_option(DEFAULT_PROTOCOL_NETWORK_ALLOWLIST),
        "protocol_env_allowlist": text_option(DEFAULT_PROTOCOL_ENV_ALLOWLIST),
        "local_prompting_mode": {
            "default": DEFAULT_LOCAL_PROMPTING_MODE,
            "options": LOCAL_PROMPTING_MODE_OPTIONS,
            "input_style": "radio",
        },
        "local_prompting_allow_fallback": {
            "default": DEFAULT_LOCAL_PROMPTING_ALLOW_FALLBACK,
            "options": GITEA_STATE_PILOT_ENABLED_OPTIONS,
            "input_style": "radio",
        },
        "local_prompting_fallback_profile_id": text_option(DEFAULT_LOCAL_PROMPTING_FALLBACK_PROFILE_ID),
        "gitea_state_pilot_enabled": {
            "default": DEFAULT_GITEA_STATE_PILOT_ENABLED,
            "options": GITEA_STATE_PILOT_ENABLED_OPTIONS,
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


def resolve_run_ledger_mode(*values: Any) -> str:
    raw = _pick_first_non_empty(values)
    aliases = {
        "sqlite": "sqlite",
        "sql": "sqlite",
        "local": "sqlite",
        "compat": "sqlite",
        "protocol": "protocol",
        "append_only": "protocol",
        "append_only_protocol": "protocol",
        "dual_write": "dual_write",
        "dual": "dual_write",
        "mirror": "dual_write",
    }
    return aliases.get(raw, DEFAULT_RUN_LEDGER_MODE)


def resolve_protocol_timezone_setting(*values: Any) -> str:
    return resolve_protocol_timezone(*values)


def resolve_protocol_locale_setting(*values: Any) -> str:
    return resolve_protocol_locale(*values)


def resolve_protocol_network_mode_setting(*values: Any) -> str:
    return resolve_protocol_network_mode(*values)


def resolve_protocol_network_allowlist_setting(*values: Any) -> str:
    parsed = resolve_protocol_network_allowlist(*values)
    return ",".join(parsed) if parsed else ""


def resolve_protocol_env_allowlist_setting(*values: Any) -> str:
    parsed = resolve_protocol_env_allowlist(*values)
    return ",".join(parsed) if parsed else ""


def resolve_local_prompting_mode(*values: Any) -> str:
    raw = _pick_first_non_empty(values)
    aliases = {
        "shadow": "shadow",
        "compat": "compat",
        "enforce": "enforce",
    }
    return aliases.get(raw, DEFAULT_LOCAL_PROMPTING_MODE)


def resolve_local_prompting_allow_fallback(*values: Any) -> bool:
    for value in values:
        raw = _normalize(value)
        if not raw:
            continue
        if raw in {"1", "true", "yes", "on", "enabled"}:
            return True
        if raw in {"0", "false", "no", "off", "disabled"}:
            return False
    return DEFAULT_LOCAL_PROMPTING_ALLOW_FALLBACK


def resolve_local_prompting_fallback_profile_id(*values: Any) -> str:
    for value in values:
        raw = str(value or "").strip()
        if raw:
            return raw
    return DEFAULT_LOCAL_PROMPTING_FALLBACK_PROFILE_ID


def resolve_gitea_state_pilot_enabled(*values: Any) -> bool:
    for value in values:
        raw = _normalize(value)
        if not raw:
            continue
        if raw in {"1", "true", "yes", "on", "enabled"}:
            return True
        if raw in {"0", "false", "no", "off", "disabled"}:
            return False
    return DEFAULT_GITEA_STATE_PILOT_ENABLED


def _resolve_numeric_setting(
    *,
    values: Iterable[Any],
    parser: Callable[[str], int | float],
    minimum: int | float,
    default: int | float,
) -> int | float:
    for value in values:
        raw = str(value or "").strip()
        if not raw:
            continue
        try:
            parsed = parser(raw)
        except ValueError:
            continue
        return max(minimum, parsed)
    return default


def resolve_gitea_worker_max_iterations(*values: Any) -> int:
    return int(
        _resolve_numeric_setting(
            values=values,
            parser=int,
            minimum=1,
            default=DEFAULT_GITEA_WORKER_MAX_ITERATIONS,
        )
    )


def resolve_gitea_worker_max_idle_streak(*values: Any) -> int:
    return int(
        _resolve_numeric_setting(
            values=values,
            parser=int,
            minimum=1,
            default=DEFAULT_GITEA_WORKER_MAX_IDLE_STREAK,
        )
    )


def resolve_gitea_worker_max_duration_seconds(*values: Any) -> float:
    return float(
        _resolve_numeric_setting(
            values=values,
            parser=float,
            minimum=0.0,
            default=DEFAULT_GITEA_WORKER_MAX_DURATION_SECONDS,
        )
    )


def resolve_protocol_determinism_controls(
    *,
    timezone_values: Iterable[Any] = (),
    locale_values: Iterable[Any] = (),
    network_mode_values: Iterable[Any] = (),
    network_allowlist_values: Iterable[Any] = (),
    clock_mode_values: Iterable[Any] = (),
    clock_artifact_ref_values: Iterable[Any] = (),
    env_allowlist_values: Iterable[Any] = (),
    environment: dict[str, str] | None = None,
) -> Dict[str, Any]:
    timezone = resolve_protocol_timezone(*list(timezone_values))
    locale = resolve_protocol_locale(*list(locale_values))
    network_mode = resolve_protocol_network_mode(*list(network_mode_values))
    network_allowlist = resolve_protocol_network_allowlist(*list(network_allowlist_values))
    clock_mode = resolve_protocol_clock_mode(*list(clock_mode_values))
    clock_artifact_ref = resolve_protocol_clock_artifact_ref(*list(clock_artifact_ref_values))
    env_allowlist = resolve_protocol_env_allowlist(*list(env_allowlist_values))
    return build_determinism_controls(
        timezone=timezone,
        locale=locale,
        network_mode=network_mode,
        network_allowlist=network_allowlist,
        clock_mode=clock_mode,
        clock_artifact_ref=clock_artifact_ref,
        env_allowlist=env_allowlist,
        environment=environment,
    )
