import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, UTC
from typing import Any, Optional

from fastapi import FastAPI, WebSocketDisconnect, HTTPException, APIRouter, Depends, Security, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
import os

from orket import __version__
from orket.logging import subscribe_to_events, unsubscribe_from_events, log_event
from orket.state import runtime_state
from orket.hardware import get_metrics_snapshot
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.time_utils import now_local
from orket.settings import load_user_settings, save_user_settings, load_user_preferences
from orket.extensions import ExtensionManager
from orket.orchestration.models import ModelSelector
from orket.streaming import (
    CommitIntent,
    CommitOrchestrator,
    InteractionManager,
    StreamBus,
    StreamBusConfig,
)
from orket.workloads import is_builtin_workload, run_builtin_workload, validate_builtin_workload_start
from orket.interfaces.routers.kernel import build_kernel_router
from orket.interfaces.routers.cards import build_cards_router
from orket.interfaces.routers.settings import build_settings_router
from orket.interfaces.routers.system import build_system_router
from orket.interfaces.routers.sessions import build_sessions_router
from orket.interfaces.routers.companion import build_companion_router
from orket.interfaces.routers.streaming import register_streaming_routes
from orket.application.services.companion_runtime_service import CompanionRuntimeService
from orket.application.services.runtime_policy import (
    allowed_architecture_patterns,
    is_microservices_pilot_stable,
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


def _resolve_api_runtime_node() -> Any:
    return DecisionNodeRegistry().resolve_api_runtime()


def _validate_session_path(session_id: str) -> Path:
    """Validate session_id does not traverse outside the runs directory."""
    base = (PROJECT_ROOT / "workspace" / "runs").resolve()
    candidate = (base / session_id).resolve()
    if not candidate.is_relative_to(base):
        raise HTTPException(status_code=400, detail="Invalid session_id")
    return candidate


def _resolve_method(target: object, invocation: dict, error_prefix: str):
    method_name = invocation["method_name"]
    method = getattr(target, method_name, None)
    if method is None:
        detail = invocation.get("unsupported_detail")
        if detail:
            raise HTTPException(status_code=400, detail=detail)
        raise HTTPException(status_code=400, detail=f"Unsupported {error_prefix} method '{method_name}'.")
    return method


async def _invoke_async_method(target: object, invocation: dict, error_prefix: str):
    method = _resolve_method(target, invocation, error_prefix)
    return await method(*invocation.get("args", []), **invocation.get("kwargs", {}))


async def _schedule_async_invocation_task(
    target: object,
    invocation: dict,
    error_prefix: str,
    session_id: str,
):
    method = _resolve_method(target, invocation, error_prefix)
    task = asyncio.create_task(method(*invocation.get("args", []), **invocation.get("kwargs", {})))
    await runtime_state.add_task(session_id, task)

    # Always remove completed/canceled tasks to keep active task tracking accurate.
    def _cleanup(_done_task: asyncio.Task):
        asyncio.create_task(runtime_state.remove_task(session_id))

    task.add_done_callback(_cleanup)


def _invoke_sync_method(target: object, invocation: dict, error_prefix: str):
    method = _resolve_method(target, invocation, error_prefix)
    return method(*invocation.get("args", []), **invocation.get("kwargs", {}))


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


def _normalize_role_name(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _parse_roles_filter(roles: Optional[str]) -> list[str]:
    if not roles:
        return []
    parsed: list[str] = []
    for token in roles.split(","):
        role = _normalize_role_name(token)
        if role and role not in parsed:
            parsed.append(role)
    return parsed


def _discover_active_roles(model_root: Path) -> list[str]:
    team_roles: set[str] = set()
    for team_file in sorted(model_root.glob("*/teams/*.json")):
        try:
            payload = json.loads(team_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        declared_roles = payload.get("roles")
        if isinstance(declared_roles, dict):
            for role_name in declared_roles.keys():
                role = _normalize_role_name(role_name)
                if role:
                    team_roles.add(role)

        seats = payload.get("seats")
        if not isinstance(seats, dict):
            continue
        for seat in seats.values():
            if not isinstance(seat, dict):
                continue
            for role_name in seat.get("roles", []) or []:
                role = _normalize_role_name(role_name)
                if role:
                    team_roles.add(role)

    if team_roles:
        return sorted(team_roles)

    fallback_roles: list[str] = []
    for role_file in sorted((model_root / "core" / "roles").glob("*.json")):
        role = _normalize_role_name(role_file.stem)
        if role:
            fallback_roles.append(role)
    return fallback_roles


def _load_role_catalog(model_root: Path) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for role_file in sorted(model_root.glob("*/roles/*.json")):
        try:
            payload = json.loads(role_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        role_name = _normalize_role_name(payload.get("name") or role_file.stem)
        if not role_name:
            continue
        catalog[role_name] = {
            "name": str(payload.get("name") or role_name),
            "description": payload.get("description"),
            "tools": list(payload.get("tools") or []),
        }
    return catalog


def _discover_team_topology(model_root: Path) -> list[dict[str, Any]]:
    role_catalog = _load_role_catalog(model_root)
    teams: list[dict[str, Any]] = []
    for team_file in sorted(model_root.glob("*/teams/*.json")):
        department = team_file.parent.parent.name
        team_id = team_file.stem
        try:
            payload = json.loads(team_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        seats_payload = payload.get("seats")
        seats: list[dict[str, Any]] = []
        referenced_roles: set[str] = set()
        if isinstance(seats_payload, dict):
            for seat_id, seat_value in seats_payload.items():
                seat = seat_value if isinstance(seat_value, dict) else {}
                raw_roles = list(seat.get("roles") or [])
                normalized_roles = [_normalize_role_name(role) for role in raw_roles if _normalize_role_name(role)]
                for role in normalized_roles:
                    referenced_roles.add(role)
                seats.append(
                    {
                        "seat_id": str(seat_id),
                        "name": seat.get("name"),
                        "roles": normalized_roles,
                    }
                )

        declared_roles: dict[str, Any] = payload.get("roles") if isinstance(payload.get("roles"), dict) else {}
        role_items: list[dict[str, Any]] = []
        all_roles = sorted(
            set(referenced_roles)
            | {_normalize_role_name(role) for role in declared_roles.keys() if _normalize_role_name(role)}
        )
        for role_name in all_roles:
            declared = declared_roles.get(role_name)
            declared = declared if isinstance(declared, dict) else {}
            catalog_entry = role_catalog.get(role_name, {})
            role_items.append(
                {
                    "role": role_name,
                    "name": declared.get("name") or catalog_entry.get("name") or role_name,
                    "description": declared.get("description") or catalog_entry.get("description"),
                    "tools": list(declared.get("tools") or catalog_entry.get("tools") or []),
                    "source": ("team" if bool(declared) else ("catalog" if bool(catalog_entry) else "seat_reference")),
                }
            )

        teams.append(
            {
                "department": department,
                "team_id": team_id,
                "name": payload.get("name") or team_id,
                "description": payload.get("description"),
                "seats": sorted(seats, key=lambda item: item["seat_id"]),
                "roles": role_items,
            }
        )
    return teams


# Security dependency
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def _read_api_key_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _is_companion_route(path: str) -> bool:
    normalized_path = str(path or "").strip()
    return normalized_path.startswith("/v1/companion") or normalized_path.startswith("/api/v1/companion")


def _read_bool_env(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _is_companion_key_strict_enabled() -> bool:
    return _read_bool_env("ORKET_COMPANION_KEY_STRICT", default=False)


def _log_api_auth_rejection(
    *,
    request_path: str,
    route_class: str,
    reason: str,
    provided_key_present: bool,
    companion_key_configured: bool,
    companion_key_strict: bool,
) -> None:
    log_event(
        "api_auth_rejected",
        {
            "route_class": route_class,
            "reason": reason,
            "request_path": request_path,
            "provided_key_present": provided_key_present,
            "companion_key_configured": companion_key_configured,
            "companion_key_strict": companion_key_strict,
        },
        PROJECT_ROOT,
    )


def _is_companion_key_valid(
    *,
    provided_key: str | None,
    default_key: str | None,
    companion_key: str | None,
    companion_key_strict: bool,
) -> bool:
    if companion_key:
        if provided_key == companion_key:
            return True
        # Allow primary host key for trusted operator/admin access.
        if not companion_key_strict and default_key and provided_key == default_key:
            return True
        return False
    return api_runtime_node.is_api_key_valid(default_key, provided_key)


async def get_api_key(request: Request, api_key_header: str | None = Security(api_key_header)):
    default_key = _read_api_key_env("ORKET_API_KEY")
    companion_key = _read_api_key_env("ORKET_COMPANION_API_KEY")
    companion_key_strict = _is_companion_key_strict_enabled()
    request_path = str(request.url.path or "")
    provided_key_present = bool(str(api_key_header or "").strip())

    if _is_companion_route(request_path):
        if _is_companion_key_valid(
            provided_key=api_key_header,
            default_key=default_key,
            companion_key=companion_key,
            companion_key_strict=companion_key_strict,
        ):
            return api_key_header
        reason = "invalid_or_missing_key_for_companion_route"
        if companion_key and companion_key_strict and api_key_header and default_key and api_key_header == default_key:
            reason = "default_key_rejected_on_companion_route_strict"
        _log_api_auth_rejection(
            request_path=request_path,
            route_class="companion",
            reason=reason,
            provided_key_present=provided_key_present,
            companion_key_configured=bool(companion_key),
            companion_key_strict=companion_key_strict,
        )
    elif api_runtime_node.is_api_key_valid(default_key, api_key_header):
        return api_key_header
    else:
        reason = "invalid_or_missing_key_for_core_route"
        if companion_key and api_key_header == companion_key:
            reason = "companion_key_rejected_on_core_route"
        _log_api_auth_rejection(
            request_path=request_path,
            route_class="core",
            reason=reason,
            provided_key_present=provided_key_present,
            companion_key_configured=bool(companion_key),
            companion_key_strict=companion_key_strict,
        )

    raise HTTPException(
        status_code=403,
        detail=api_runtime_node.api_key_invalid_detail(),
    )


# --- Lifespan ---


def _on_log_record_factory(loop: asyncio.AbstractEventLoop):
    def on_log_record(record):
        loop.call_soon_threadsafe(runtime_state.event_queue.put_nowait, record)

    return on_log_record


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from orket.utils import ensure_log_dir

    ensure_log_dir()
    broadcaster_task = asyncio.create_task(event_broadcaster())
    loop = asyncio.get_running_loop()
    log_subscriber = _on_log_record_factory(loop)
    subscribe_to_events(log_subscriber)
    expected_key = _read_api_key_env("ORKET_API_KEY")
    companion_key = _read_api_key_env("ORKET_COMPANION_API_KEY")
    companion_key_strict = _is_companion_key_strict_enabled()
    insecure_bypass = os.getenv("ORKET_ALLOW_INSECURE_NO_API_KEY", "").strip().lower() in {"1", "true", "yes", "on"}
    log_event(
        "api_security_posture",
        {
            "api_key_configured": bool(expected_key),
            "companion_api_key_configured": bool(companion_key),
            "companion_api_key_scoped": bool(companion_key and companion_key != expected_key),
            "companion_key_strict": companion_key_strict,
            "insecure_no_api_key_bypass": insecure_bypass,
        },
        PROJECT_ROOT,
    )
    if insecure_bypass:
        log_event(
            "api_security_warning",
            {"message": "ORKET_ALLOW_INSECURE_NO_API_KEY is enabled; /v1 auth is bypassed without ORKET_API_KEY."},
            PROJECT_ROOT,
        )
    try:
        yield
    finally:
        unsubscribe_from_events(log_subscriber)
        broadcaster_task.cancel()
        try:
            await broadcaster_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Orket API", version=__version__, lifespan=lifespan)
# Apply auth to all v1 endpoints if configured
v1_router = APIRouter(prefix="/v1", dependencies=[Depends(get_api_key)])
companion_api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_api_key)])

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
api_runtime_node = _resolve_api_runtime_node()
origins_str = os.getenv("ORKET_ALLOWED_ORIGINS", api_runtime_node.default_allowed_origins_value())
origins = api_runtime_node.parse_allowed_origins(origins_str)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

engine = api_runtime_node.create_engine(api_runtime_node.resolve_api_workspace(PROJECT_ROOT))
stream_bus: StreamBus | None = None
interaction_manager: InteractionManager | None = None
extension_manager: ExtensionManager | None = None
companion_service: CompanionRuntimeService | None = None


def _build_stream_bus_from_env() -> StreamBus:
    return StreamBus(
        StreamBusConfig(
            best_effort_max_events_per_turn=int(os.getenv("ORKET_STREAM_BEST_EFFORT_MAX_EVENTS_PER_TURN", "256")),
            bounded_max_events_per_turn=int(os.getenv("ORKET_STREAM_BOUNDED_MAX_EVENTS_PER_TURN", "128")),
            max_bytes_per_turn_queue=int(os.getenv("ORKET_STREAM_MAX_BYTES_PER_TURN_QUEUE", "1000000")),
        )
    )


def _get_stream_bus() -> StreamBus:
    global stream_bus
    if stream_bus is None:
        stream_bus = _build_stream_bus_from_env()
    return stream_bus


def _get_interaction_manager() -> InteractionManager:
    global interaction_manager
    if interaction_manager is None:
        interaction_manager = InteractionManager(
            bus=_get_stream_bus(),
            commit_orchestrator=CommitOrchestrator(project_root=PROJECT_ROOT),
            project_root=PROJECT_ROOT,
        )
    return interaction_manager


def _get_extension_manager() -> ExtensionManager:
    global extension_manager
    if extension_manager is None:
        extension_manager = ExtensionManager(project_root=PROJECT_ROOT)
    return extension_manager


def _get_companion_service() -> CompanionRuntimeService:
    global companion_service
    if companion_service is None:
        companion_service = CompanionRuntimeService(project_root=PROJECT_ROOT)
    return companion_service


# --- System Endpoints ---


@app.get("/health")
async def health():
    return {"status": "ok", "organization": "Orket"}


# --- v1 Endpoints ---


@v1_router.get("/version")
async def get_version():
    return {"version": __version__, "api": "v1"}


v1_router.include_router(build_kernel_router(lambda: engine))
v1_router.include_router(build_cards_router(lambda: engine, api_runtime_node))
v1_router.include_router(
    build_settings_router(
        settings_order=SETTINGS_ORDER,
        settings_schema=SETTINGS_SCHEMA,
        runtime_policy_options=lambda: runtime_policy_options(),
        load_user_settings=lambda: load_user_settings(),
        save_user_settings=lambda settings: save_user_settings(settings),
        runtime_policy_process_rules=lambda: _runtime_policy_process_rules(),
        resolve_settings_snapshot=lambda user_settings, process_rules: _resolve_settings_snapshot(
            user_settings, process_rules
        ),
        parse_setting_value=lambda field, value: _parse_setting_value(field, value),
        settings_validation_error=lambda errors: _settings_validation_error(errors),
        is_microservices_unlocked=lambda: is_microservices_unlocked(),
        resolve_architecture_mode=lambda env_value, process_value, user_value: resolve_architecture_mode(
            env_value, process_value, user_value
        ),
        resolve_frontend_framework_mode=lambda env_value, process_value, user_value: resolve_frontend_framework_mode(
            env_value,
            process_value,
            user_value,
        ),
        resolve_project_surface_profile=lambda env_value, process_value, user_value: resolve_project_surface_profile(
            env_value,
            process_value,
            user_value,
        ),
        resolve_small_project_builder_variant=lambda env_value, process_value, user_value: (
            resolve_small_project_builder_variant(
                env_value,
                process_value,
                user_value,
            )
        ),
        resolve_state_backend_mode=lambda env_value, process_value, user_value: resolve_state_backend_mode(
            env_value,
            process_value,
            user_value,
        ),
        resolve_run_ledger_mode=lambda env_value, process_value, user_value: resolve_run_ledger_mode(
            env_value,
            process_value,
            user_value,
        ),
        resolve_protocol_timezone_setting=lambda env_value, process_value, user_value: (
            resolve_protocol_timezone_setting(
                env_value,
                process_value,
                user_value,
            )
        ),
        resolve_protocol_locale_setting=lambda env_value, process_value, user_value: resolve_protocol_locale_setting(
            env_value,
            process_value,
            user_value,
        ),
        resolve_protocol_network_mode_setting=lambda env_value, process_value, user_value: (
            resolve_protocol_network_mode_setting(
                env_value,
                process_value,
                user_value,
            )
        ),
        resolve_protocol_network_allowlist_setting=lambda env_value, process_value, user_value: (
            resolve_protocol_network_allowlist_setting(
                env_value,
                process_value,
                user_value,
            )
        ),
        resolve_protocol_env_allowlist_setting=lambda env_value, process_value, user_value: (
            resolve_protocol_env_allowlist_setting(
                env_value,
                process_value,
                user_value,
            )
        ),
        resolve_local_prompting_mode=lambda env_value, process_value, user_value: resolve_local_prompting_mode(
            env_value,
            process_value,
            user_value,
        ),
        resolve_local_prompting_allow_fallback=lambda env_value, process_value, user_value: (
            resolve_local_prompting_allow_fallback(
                env_value,
                process_value,
                user_value,
            )
        ),
        resolve_local_prompting_fallback_profile_id=lambda env_value, process_value, user_value: (
            resolve_local_prompting_fallback_profile_id(
                env_value,
                process_value,
                user_value,
            )
        ),
        resolve_gitea_state_pilot_enabled=lambda env_value, process_value, user_value: (
            resolve_gitea_state_pilot_enabled(
                env_value,
                process_value,
                user_value,
            )
        ),
        allowed_architecture_patterns=lambda: allowed_architecture_patterns(),
        is_microservices_pilot_stable=lambda: is_microservices_pilot_stable(),
    )
)
v1_router.include_router(
    build_system_router(
        project_root_getter=lambda: PROJECT_ROOT,
        runtime_state=runtime_state,
        api_runtime_node_getter=lambda: api_runtime_node,
        now_local=now_local,
        get_metrics_snapshot=get_metrics_snapshot,
        log_event=lambda name, payload, workspace: log_event(name, payload, workspace),
        model_selector_factory=lambda organization, preferences, user_settings: ModelSelector(
            organization=organization,
            preferences=preferences,
            user_settings=user_settings,
        ),
        load_user_preferences=lambda: load_user_preferences(),
        load_user_settings=lambda: load_user_settings(),
        parse_roles_filter=lambda roles: _parse_roles_filter(roles),
        discover_active_roles=lambda root: _discover_active_roles(root),
        discover_team_topology=lambda root: _discover_team_topology(root),
        invoke_async_method=_invoke_async_method,
        schedule_async_invocation_task=_schedule_async_invocation_task,
        engine_getter=lambda: engine,
    )
)
v1_router.include_router(
    build_sessions_router(
        interaction_manager_getter=lambda: _get_interaction_manager(),
        extension_manager_getter=lambda: _get_extension_manager(),
        is_builtin_workload=lambda workload_id: is_builtin_workload(workload_id),
        validate_builtin_workload_start=lambda **kwargs: validate_builtin_workload_start(**kwargs),
        run_builtin_workload=lambda **kwargs: run_builtin_workload(**kwargs),
        commit_intent_factory=lambda reason: CommitIntent(type="decision", ref=f"fail_closed:{reason}"),
    )
)
v1_router.include_router(build_companion_router(service_getter=lambda: _get_companion_service()))
companion_api_router.include_router(build_companion_router(service_getter=lambda: _get_companion_service()))


def _normalize_setting_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _parse_setting_value(field: str, value: Any) -> Any | None:
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


def _runtime_policy_process_rules() -> dict[str, Any]:
    if engine.org and isinstance(getattr(engine.org, "process_rules", None), dict):
        return dict(engine.org.process_rules)
    return {}


def _resolve_runtime_setting_value(field: str, env_value: Any, process_value: Any, user_value: Any) -> Any:
    if field == "architecture_mode":
        return resolve_architecture_mode(env_value, process_value, user_value)
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


def _resolve_settings_snapshot(user_settings: dict[str, Any], process_rules: dict[str, Any]) -> dict[str, Any]:
    options = runtime_policy_options()
    snapshot: dict[str, Any] = {}
    microservices_unlocked = is_microservices_unlocked()
    for field in SETTINGS_ORDER:
        schema = SETTINGS_SCHEMA[field]
        env_value = os.environ.get(schema["env_var"], "")
        process_value = process_rules.get(field)
        user_value = user_settings.get(field)
        effective = _resolve_runtime_setting_value(field, env_value, process_value, user_value)

        source = "default"
        # Keep state backend settings stable across machines with ambient env vars.
        # API settings UX should primarily reflect explicit policy/user choices.
        if (
            field not in {"state_backend_mode", "run_ledger_mode"}
            and _parse_setting_value(field, env_value) is not None
        ):
            source = "env"
        elif _parse_setting_value(field, process_value) is not None:
            source = "process_rules"
        elif _parse_setting_value(field, user_value) is not None:
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
            requested = _parse_setting_value(field, env_value)
            if requested is None:
                requested = _parse_setting_value(field, process_value)
            if requested is None:
                requested = _parse_setting_value(field, user_value)
            if requested == "force_microservices" and not microservices_unlocked:
                entry["policy_guard"] = "microservices_locked"
        snapshot[field] = entry
    return snapshot


def _settings_validation_error(errors: list[dict[str, Any]]) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "message": "Invalid settings update",
            "errors": errors,
        },
    )


@v1_router.get("/runs")
async def list_runs():
    invocation = api_runtime_node.resolve_runs_invocation()
    return await _invoke_async_method(engine.sessions, invocation, "runs")


@v1_router.get("/runs/{session_id}")
async def get_run_detail(session_id: str):
    run_record = await engine.run_ledger.get_run(session_id)
    session = await engine.sessions.get_session(session_id)

    if run_record is None and session is None:
        raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")

    backlog = await engine.sessions.get_session_issues(session_id)
    summary = {}
    artifacts = {}
    status = None
    if isinstance(run_record, dict):
        summary = dict(run_record.get("summary_json") or {})
        artifacts = dict(run_record.get("artifact_json") or {})
        status = run_record.get("status")
    if status is None and isinstance(session, dict):
        status = session.get("status")

    return {
        "session_id": session_id,
        "status": status,
        "summary": summary,
        "artifacts": artifacts,
        "issue_count": len(backlog),
        "session": session,
        "run_ledger": run_record,
    }


@v1_router.get("/runs/{session_id}/metrics")
async def get_run_metrics(session_id: str):
    log_event("api_run_metrics", {"session_id": session_id}, PROJECT_ROOT)
    _validate_session_path(session_id)
    workspace = api_runtime_node.resolve_member_metrics_workspace(PROJECT_ROOT, session_id)
    metrics_reader = api_runtime_node.create_member_metrics_reader()
    return await asyncio.to_thread(metrics_reader, workspace)


@v1_router.get("/runs/{session_id}/token-summary")
async def get_run_token_summary(session_id: str):
    run_record = await engine.run_ledger.get_run(session_id)
    session = await engine.sessions.get_session(session_id)
    if run_record is None and session is None:
        raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")

    run_path = _validate_session_path(session_id)
    candidate_files = [PROJECT_ROOT / "workspace" / "default" / "orket.log"]
    candidate_files.append(run_path / "orket.log")

    records: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for path in candidate_files:
        path_records = await asyncio.to_thread(_read_log_records, path)
        for record in path_records:
            signature = (
                record.get("timestamp"),
                record.get("event"),
                str((record.get("data") or {}).get("turn_trace_id") or ""),
                str(record.get("role") or ""),
                str((record.get("data") or {}).get("issue_id") or ""),
            )
            if signature in seen:
                continue
            seen.add(signature)
            records.append(record)

    model_by_turn_trace: dict[str, str] = {}
    turns: list[dict[str, Any]] = []
    role_totals: dict[str, int] = {}
    model_totals: dict[str, int] = {}
    role_model_totals: dict[str, int] = {}
    total_tokens = 0

    for record in records:
        if _record_session_id(record) != session_id:
            continue
        event = str(record.get("event") or "")
        data = record.get("data", {})
        if not isinstance(data, dict):
            continue
        runtime_event = data.get("runtime_event", {})
        runtime_event = runtime_event if isinstance(runtime_event, dict) else {}
        turn_trace_id = str(runtime_event.get("turn_trace_id") or data.get("turn_trace_id") or "").strip()

        if event == "turn_start":
            selected_model = str(runtime_event.get("selected_model") or data.get("selected_model") or "").strip()
            if turn_trace_id and selected_model:
                model_by_turn_trace[turn_trace_id] = selected_model
            continue

        if event != "turn_complete":
            continue

        role = str(record.get("role") or runtime_event.get("role") or data.get("role") or "unknown").strip().lower()
        model = (
            str(
                model_by_turn_trace.get(turn_trace_id)
                or runtime_event.get("selected_model")
                or data.get("selected_model")
                or "unknown"
            )
            .strip()
            .lower()
        )
        issue_id = str(runtime_event.get("issue_id") or data.get("issue_id") or "").strip()
        turn_index_raw = runtime_event.get("turn_index") or data.get("turn_index") or 0
        try:
            turn_index = int(turn_index_raw)
        except (TypeError, ValueError):
            turn_index = 0
        tokens_total = _extract_total_tokens(runtime_event.get("tokens"))
        if not tokens_total:
            tokens_total = _extract_total_tokens(data.get("tokens"))
        if not tokens_total:
            tokens_total = _extract_total_tokens(data.get("total_tokens"))

        turn_row = {
            "turn_trace_id": turn_trace_id or None,
            "issue_id": issue_id or None,
            "turn_index": turn_index,
            "role": role,
            "model": model,
            "tokens_total": tokens_total,
        }
        turns.append(turn_row)
        total_tokens += tokens_total
        role_totals[role] = role_totals.get(role, 0) + tokens_total
        model_totals[model] = model_totals.get(model, 0) + tokens_total
        role_model_key = f"{role}:{model}"
        role_model_totals[role_model_key] = role_model_totals.get(role_model_key, 0) + tokens_total

    turns.sort(key=lambda item: (item["turn_index"], str(item["issue_id"] or ""), str(item["role"])))
    by_role = [
        {"role": role, "tokens_total": value} for role, value in sorted(role_totals.items(), key=lambda item: item[0])
    ]
    by_model = [
        {"model": model, "tokens_total": value}
        for model, value in sorted(model_totals.items(), key=lambda item: item[0])
    ]

    by_role_model: list[dict[str, Any]] = []
    for key, value in sorted(role_model_totals.items(), key=lambda item: item[0]):
        role, model = key.split(":", 1)
        by_role_model.append({"role": role, "model": model, "tokens_total": value})

    return {
        "session_id": session_id,
        "total_tokens": total_tokens,
        "turn_count": len(turns),
        "by_role": by_role,
        "by_model": by_model,
        "by_role_model": by_role_model,
        "turns": turns,
    }


def _collect_replay_turns(session_id: str, role: Optional[str] = None) -> list[dict[str, Any]]:
    run_path = _validate_session_path(session_id)
    candidate_files = [PROJECT_ROOT / "workspace" / "default" / "orket.log"]
    candidate_files.append(run_path / "orket.log")

    records: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for path in candidate_files:
        for record in _read_log_records(path):
            signature = (
                record.get("timestamp"),
                record.get("event"),
                str((record.get("data") or {}).get("turn_trace_id") or ""),
                str(record.get("role") or ""),
                str((record.get("data") or {}).get("issue_id") or ""),
                str((record.get("data") or {}).get("turn_index") or ""),
            )
            if signature in seen:
                continue
            seen.add(signature)
            records.append(record)

    model_by_turn_trace: dict[str, str] = {}
    turns: list[dict[str, Any]] = []
    role_filter = str(role or "").strip().lower()

    for record in records:
        if _record_session_id(record) != session_id:
            continue
        event = str(record.get("event") or "")
        data = record.get("data", {})
        if not isinstance(data, dict):
            continue
        runtime_event = data.get("runtime_event", {})
        runtime_event = runtime_event if isinstance(runtime_event, dict) else {}
        turn_trace_id = str(runtime_event.get("turn_trace_id") or data.get("turn_trace_id") or "").strip()

        if event == "turn_start":
            selected_model = str(runtime_event.get("selected_model") or data.get("selected_model") or "").strip()
            if turn_trace_id and selected_model:
                model_by_turn_trace[turn_trace_id] = selected_model
            continue

        if event != "turn_complete":
            continue

        normalized_role = (
            str(record.get("role") or runtime_event.get("role") or data.get("role") or "unknown").strip().lower()
        )
        if role_filter and normalized_role != role_filter:
            continue

        issue_id = str(runtime_event.get("issue_id") or data.get("issue_id") or "").strip()
        turn_index_raw = runtime_event.get("turn_index") or data.get("turn_index") or 0
        try:
            turn_index = int(turn_index_raw)
        except (TypeError, ValueError):
            turn_index = 0

        turns.append(
            {
                "session_id": session_id,
                "issue_id": issue_id or None,
                "turn_index": turn_index,
                "role": normalized_role,
                "turn_trace_id": turn_trace_id or None,
                "selected_model": str(
                    model_by_turn_trace.get(turn_trace_id)
                    or runtime_event.get("selected_model")
                    or data.get("selected_model")
                    or ""
                ).strip()
                or None,
                "timestamp": str(record.get("timestamp") or ""),
            }
        )

    turns.sort(key=lambda item: (item["turn_index"], str(item["issue_id"] or ""), str(item["role"]), item["timestamp"]))
    return turns


@v1_router.get("/runs/{session_id}/replay")
async def list_run_replay_turns(session_id: str, role: Optional[str] = None):
    run_record = await engine.run_ledger.get_run(session_id)
    session = await engine.sessions.get_session(session_id)
    if run_record is None and session is None:
        raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")
    turns = await asyncio.to_thread(_collect_replay_turns, session_id=session_id, role=role)
    return {
        "session_id": session_id,
        "turn_count": len(turns),
        "filters": {"role": role or None},
        "turns": turns,
    }


@v1_router.get("/runs/{session_id}/backlog")
async def get_backlog(session_id: str):
    log_event("api_backlog", {"session_id": session_id}, PROJECT_ROOT)
    invocation = api_runtime_node.resolve_backlog_invocation(session_id)
    return await _invoke_async_method(engine.sessions, invocation, "backlog")


@v1_router.get("/runs/{session_id}/execution-graph")
async def get_execution_graph(session_id: str):
    run_record = await engine.run_ledger.get_run(session_id)
    session = await engine.sessions.get_session(session_id)
    if run_record is None and session is None:
        raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")

    backlog = await engine.sessions.get_session_issues(session_id)
    graph = await asyncio.to_thread(_build_execution_graph, backlog, session_id)
    compact_edges = [
        {"source": str(edge.get("source") or ""), "target": str(edge.get("target") or "")}
        for edge in list(graph.get("edges") or [])
        if str(edge.get("source") or "").strip() and str(edge.get("target") or "").strip()
    ]
    payload = {
        "session_id": session_id,
        "node_count": len(graph["nodes"]),
        "edge_count": len(compact_edges),
        "edges_detailed": graph["edges"],
        **graph,
        "edges": compact_edges,
    }
    await asyncio.to_thread(_persist_execution_graph_snapshot, session_id, payload)
    return payload


@v1_router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str):
    log_event("api_session_detail", {"session_id": session_id}, PROJECT_ROOT)
    invocation = api_runtime_node.resolve_session_detail_invocation(session_id)
    session = await _invoke_async_method(engine.sessions, invocation, "session")
    if not session:
        raise HTTPException(**api_runtime_node.session_detail_not_found_error(session_id))
    return session


@v1_router.get("/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    session = await engine.sessions.get_session(session_id)
    if not session:
        raise HTTPException(**api_runtime_node.session_detail_not_found_error(session_id))

    run_record = await engine.run_ledger.get_run(session_id)
    backlog = await engine.sessions.get_session_issues(session_id)
    task = await runtime_state.get_task(session_id)
    is_active = bool(task and not task.done())

    backlog_counts: dict[str, int] = {}
    for issue in backlog:
        issue_status = str(issue.get("status") or "unknown")
        backlog_counts[issue_status] = backlog_counts.get(issue_status, 0) + 1

    return {
        "session_id": session_id,
        "active": is_active,
        "status": (run_record or {}).get("status", session.get("status")),
        "task_state": (
            "running"
            if is_active
            else (
                "completed"
                if task and task.done() and not task.cancelled()
                else ("canceled" if task and task.cancelled() else "idle")
            )
        ),
        "backlog": {
            "count": len(backlog),
            "by_status": backlog_counts,
        },
        "summary": dict((run_record or {}).get("summary_json") or {}),
        "artifacts": dict((run_record or {}).get("artifact_json") or {}),
    }


@v1_router.post("/sessions/{session_id}/halt")
async def halt_session(session_id: str):
    run_record = await engine.run_ledger.get_run(session_id)
    if run_record is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    await engine.halt_session(session_id)
    task = await runtime_state.get_task(session_id)
    return {
        "ok": True,
        "session_id": session_id,
        "active": bool(task and not task.done()),
    }


@v1_router.get("/sessions/{session_id}/replay")
async def replay_session_turn(
    session_id: str,
    issue_id: Optional[str] = None,
    turn_index: Optional[int] = Query(default=None, ge=1),
    role: Optional[str] = None,
):
    if not issue_id and turn_index is None:
        return await list_run_replay_turns(session_id=session_id, role=role)
    if bool(issue_id) != bool(turn_index):
        raise HTTPException(
            status_code=422,
            detail="Both 'issue_id' and 'turn_index' are required for targeted replay.",
        )
    try:
        replay = engine.replay_turn(
            session_id=session_id,
            issue_id=str(issue_id),
            turn_index=int(turn_index),
            role=role,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return replay


@v1_router.get("/sessions/{session_id}/snapshot")
async def get_session_snapshot(session_id: str):
    log_event("api_session_snapshot", {"session_id": session_id}, PROJECT_ROOT)
    invocation = api_runtime_node.resolve_session_snapshot_invocation(session_id)
    snapshot = await _invoke_async_method(engine.snapshots, invocation, "snapshot")
    if not snapshot:
        raise HTTPException(**api_runtime_node.session_snapshot_not_found_error(session_id))
    return snapshot


@v1_router.get("/sandboxes")
async def list_sandboxes():
    invocation = api_runtime_node.resolve_sandboxes_list_invocation()
    return await _invoke_async_method(engine, invocation, "sandboxes")


@v1_router.post("/sandboxes/{sandbox_id}/stop")
async def stop_sandbox(sandbox_id: str):
    invocation = api_runtime_node.resolve_sandbox_stop_invocation(sandbox_id)
    try:
        await _invoke_async_method(engine, invocation, "sandbox stop")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@v1_router.get("/sandboxes/{sandbox_id}/logs")
async def get_sandbox_logs(sandbox_id: str, service: Optional[str] = None):
    pipeline = api_runtime_node.create_execution_pipeline(api_runtime_node.resolve_sandbox_workspace(PROJECT_ROOT))
    invocation = api_runtime_node.resolve_sandbox_logs_invocation(sandbox_id, service)
    logs = await asyncio.to_thread(
        _invoke_sync_method,
        pipeline.sandbox_orchestrator,
        invocation,
        "sandbox logs",
    )
    return {"logs": logs}


def _coerce_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: '{value}'")


def _build_execution_graph(backlog: list[dict[str, Any]], session_id: str) -> dict[str, Any]:
    items = [item for item in backlog if isinstance(item, dict)]
    index_by_id: dict[str, int] = {}
    status_by_id: dict[str, str] = {}
    for index, item in enumerate(items):
        issue_id = str(item.get("id") or "").strip()
        if not issue_id or issue_id in index_by_id:
            continue
        index_by_id[issue_id] = index
        status_by_id[issue_id] = str(item.get("status") or "unknown").strip().lower()

    edges: list[dict[str, Any]] = []
    adjacency: dict[str, list[str]] = {issue_id: [] for issue_id in index_by_id}
    in_degree: dict[str, int] = {issue_id: 0 for issue_id in index_by_id}
    dependency_satisfied_statuses = {"done", "guard_approved", "archived"}

    for item in items:
        issue_id = str(item.get("id") or "").strip()
        if issue_id not in index_by_id:
            continue
        for raw_dep in list(item.get("depends_on") or []):
            dep_id = str(raw_dep or "").strip()
            if not dep_id or dep_id not in index_by_id:
                continue
            edges.append({"source": dep_id, "target": issue_id, "kind": "depends_on"})
            adjacency[dep_id].append(issue_id)
            in_degree[issue_id] += 1

    edge_keys = {(edge["source"], edge["target"], str(edge.get("kind") or "depends_on")) for edge in edges}

    # Parent-child relationships (when present) are modeled as spawn edges.
    for item in items:
        issue_id = str(item.get("id") or "").strip()
        parent_id = str(item.get("parent_id") or "").strip()
        if issue_id not in index_by_id or parent_id not in index_by_id or parent_id == issue_id:
            continue
        key = (parent_id, issue_id, "spawn")
        if key in edge_keys:
            continue
        edge_keys.add(key)
        edges.append({"source": parent_id, "target": issue_id, "kind": "spawn"})

    for handoff in _derive_handoff_edges(session_id, index_by_id):
        key = (handoff["source"], handoff["target"], "handoff")
        if key in edge_keys:
            continue
        edge_keys.add(key)
        edges.append(handoff)

    topo_queue = sorted(
        [issue_id for issue_id, degree in in_degree.items() if degree == 0],
        key=lambda issue_id: index_by_id[issue_id],
    )
    topo_in_degree = dict(in_degree)
    execution_order: list[str] = []
    while topo_queue:
        current = topo_queue.pop(0)
        execution_order.append(current)
        for neighbor in sorted(adjacency.get(current, []), key=lambda issue_id: index_by_id[issue_id]):
            topo_in_degree[neighbor] -= 1
            if topo_in_degree[neighbor] == 0:
                topo_queue.append(neighbor)
        topo_queue.sort(key=lambda issue_id: index_by_id[issue_id])

    has_cycle = len(execution_order) != len(index_by_id)
    cycle_nodes: list[str] = []
    if has_cycle:
        cycle_nodes = sorted(
            [issue_id for issue_id, degree in topo_in_degree.items() if degree > 0],
            key=lambda issue_id: index_by_id[issue_id],
        )

    nodes: list[dict[str, Any]] = []
    for item in items:
        issue_id = str(item.get("id") or "").strip()
        if issue_id not in index_by_id:
            continue
        depends_on = [str(dep).strip() for dep in list(item.get("depends_on") or []) if str(dep).strip()]
        unresolved_dependencies = [dep for dep in depends_on if dep not in index_by_id]
        dependency_statuses: dict[str, str] = {}
        blocked_by: list[str] = []
        for dep in depends_on:
            dep_status = status_by_id.get(dep, "missing")
            dependency_statuses[dep] = dep_status
            if dep_status not in dependency_satisfied_statuses:
                blocked_by.append(dep)
        status = str(item.get("status") or "unknown").strip().lower()
        blocked = bool(blocked_by) and status not in {"done", "archived", "guard_approved"}
        nodes.append(
            {
                "id": issue_id,
                "summary": item.get("summary"),
                "seat": item.get("seat"),
                "status": status,
                "depends_on": depends_on,
                "dependency_count": len(depends_on),
                "dependency_statuses": dependency_statuses,
                "blocked": blocked,
                "blocked_by": blocked_by,
                "unresolved_dependencies": unresolved_dependencies,
                "in_degree": in_degree[issue_id],
                "order_index": index_by_id[issue_id],
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "execution_order": execution_order,
        "has_cycle": has_cycle,
        "cycle_nodes": cycle_nodes,
    }


def _derive_handoff_edges(session_id: str, index_by_id: dict[str, int]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    run_path = _validate_session_path(session_id)
    run_log = run_path / "orket.log"
    default_log = PROJECT_ROOT / "workspace" / "default" / "orket.log"

    for path in [run_log, default_log]:
        records.extend(_read_log_records(path))

    turns: list[tuple[int, str, str]] = []
    for record in records:
        if _record_session_id(record) != session_id:
            continue
        if str(record.get("event") or "").strip() != "turn_complete":
            continue

        data = record.get("data", {})
        data = data if isinstance(data, dict) else {}
        runtime_event = data.get("runtime_event", {})
        runtime_event = runtime_event if isinstance(runtime_event, dict) else {}

        issue_id = str(runtime_event.get("issue_id") or data.get("issue_id") or "").strip()
        if not issue_id or issue_id not in index_by_id:
            continue

        try:
            turn_index = int(runtime_event.get("turn_index") or data.get("turn_index") or 0)
        except (TypeError, ValueError):
            turn_index = 0

        timestamp = str(record.get("timestamp") or "")
        turns.append((turn_index, timestamp, issue_id))

    turns.sort(key=lambda row: (row[0], row[1]))

    handoff_edges: list[dict[str, Any]] = []
    previous_issue: Optional[str] = None
    for turn_index, timestamp, issue_id in turns:
        if previous_issue and previous_issue != issue_id:
            handoff_edges.append(
                {
                    "source": previous_issue,
                    "target": issue_id,
                    "kind": "handoff",
                    "source_event": "turn_complete",
                    "timestamp": timestamp,
                    "turn_index": turn_index,
                }
            )
        previous_issue = issue_id

    return handoff_edges


def _persist_execution_graph_snapshot(session_id: str, payload: dict[str, Any]) -> None:
    try:
        run_path = _validate_session_path(session_id)
        path = run_path / "agent_output" / "observability" / "execution_graph_snapshot.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, TypeError, ValueError):
        # Snapshot persistence should never fail the API response path.
        return


def _record_session_id(record: dict[str, Any]) -> str:
    data = record.get("data", {})
    if isinstance(data, dict):
        runtime_event = data.get("runtime_event", {})
        if isinstance(runtime_event, dict):
            return str(runtime_event.get("session_id") or "")
        return str(data.get("session_id") or "")
    return ""


def _extract_total_tokens(value: Any) -> int:
    if isinstance(value, dict):
        raw = value.get("total_tokens")
    else:
        raw = value
    try:
        parsed = int(raw or 0)
    except (TypeError, ValueError):
        parsed = 0
    return parsed if parsed > 0 else 0


def _read_log_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


@v1_router.get("/logs")
async def list_logs(
    session_id: Optional[str] = None,
    event: Optional[str] = None,
    role: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
):
    start_dt = _coerce_datetime(start_time)
    end_dt = _coerce_datetime(end_time)

    candidate_files = [PROJECT_ROOT / "workspace" / "default" / "orket.log"]
    if session_id:
        run_path = _validate_session_path(session_id)
        candidate_files.append(run_path / "orket.log")

    records: list[dict] = []
    for path in candidate_files:
        records.extend(await asyncio.to_thread(_read_log_records, path))

    filtered: list[dict] = []
    for record in records:
        rec_event = str(record.get("event") or "")
        rec_role = str(record.get("role") or "")
        rec_timestamp = str(record.get("timestamp") or "")
        rec_session_id = _record_session_id(record)

        if session_id and rec_session_id != session_id:
            continue
        if event and rec_event != event:
            continue
        if role and rec_role != role:
            continue

        try:
            ts_dt = datetime.fromisoformat(rec_timestamp)
        except ValueError:
            ts_dt = None
        if start_dt and (ts_dt is None or ts_dt < start_dt):
            continue
        if end_dt and (ts_dt is None or ts_dt > end_dt):
            continue

        filtered.append(record)

    filtered.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    page = filtered[offset : offset + limit]
    return {
        "items": page,
        "count": len(page),
        "total": len(filtered),
        "limit": limit,
        "offset": offset,
        "filters": {
            "session_id": session_id,
            "event": event,
            "role": role,
            "start_time": start_time,
            "end_time": end_time,
        },
    }


app.include_router(v1_router)
app.include_router(companion_api_router)


def create_api_app(project_root: Optional[Path] = None) -> FastAPI:
    global PROJECT_ROOT, engine, interaction_manager, extension_manager, stream_bus, companion_service
    if project_root is not None:
        PROJECT_ROOT = Path(project_root).resolve()
    engine = api_runtime_node.create_engine(api_runtime_node.resolve_api_workspace(PROJECT_ROOT))
    stream_bus = _build_stream_bus_from_env()
    interaction_manager = InteractionManager(
        bus=stream_bus,
        commit_orchestrator=CommitOrchestrator(project_root=PROJECT_ROOT),
        project_root=PROJECT_ROOT,
    )
    extension_manager = ExtensionManager(project_root=PROJECT_ROOT)
    companion_service = CompanionRuntimeService(project_root=PROJECT_ROOT)
    return app


# --- WS ---


async def event_broadcaster():
    while True:
        record = await runtime_state.event_queue.get()
        for ws in await runtime_state.get_websockets():
            try:
                await ws.send_json(record)
            except (WebSocketDisconnect, RuntimeError, ValueError) as exc:
                if isinstance(exc, WebSocketDisconnect) or api_runtime_node.should_remove_websocket(exc):
                    await runtime_state.remove_websocket(ws)
        runtime_state.event_queue.task_done()


register_streaming_routes(
    app,
    api_key_name=API_KEY_NAME,
    api_runtime_node_getter=lambda: api_runtime_node,
    interaction_manager_getter=lambda: _get_interaction_manager(),
    stream_bus_getter=lambda: _get_stream_bus(),
    runtime_state=runtime_state,
    project_root_getter=lambda: PROJECT_ROOT,
    log_event=log_event,
)
