import asyncio
import hashlib
import json
import logging
import os
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, TypeVar, cast

from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Query, Request, Security, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader

from orket import __version__
from orket.application.interactions.manager import InteractionManager
from orket.application.services import api_policy_input_service as api_policy
from orket.application.services.api_runtime_host_service import ApiRuntimeHostService
from orket.application.services.api_runtime_preparation import build_api_runtime_preparation
from orket.application.services.api_startup_service import api_runtime_lifespan
from orket.application.services.execution_graph_service import (
    execution_graph_payload,
    inspect_execution_graph,
    persist_execution_graph_snapshot,
)
from orket.application.services.outward_run_execution_service import (
    OutwardRunExecutionValidationError,
)
from orket.application.services.outward_run_inspection_service import (
    OutwardRunInspectionError,
)
from orket.application.services.outward_run_service import (
    OutwardRunConflictError,
    OutwardRunValidationError,
)
from orket.application.services.run_ledger_summary_projection import (
    validated_run_ledger_record_projection,
)
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_inspection_service import read_runtime_replay, read_runtime_sandbox_logs
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
from orket.application.services.runtime_result_lifetime import open_runtime_owner
from orket.interfaces.api_runtime_context import (
    ApiAppRuntimeContext,
    get_api_runtime_context,
    set_api_runtime_context,
)
from orket.interfaces.api_transport_composition import register_api_transport
from orket.interfaces.routers.card_authoring import build_card_authoring_router
from orket.interfaces.routers.cards import build_cards_router
from orket.interfaces.routers.extension_runtime import build_extension_runtime_router
from orket.interfaces.routers.flows import build_flows_router
from orket.interfaces.routers.governed_agents import build_governed_agents_router
from orket.interfaces.routers.kernel import build_kernel_router
from orket.interfaces.routers.outward_ledger import build_outward_ledger_router
from orket.interfaces.routers.runs import build_runs_router
from orket.interfaces.routers.sessions import build_sessions_router
from orket.interfaces.routers.settings import build_settings_router
from orket.interfaces.routers.system import build_system_router
from orket.kernel.v1.outbound_policy_gate import (
    apply_outbound_policy_gate,
    merge_outbound_policy_config,
)
from orket.settings import load_user_settings_async, save_user_settings_async

LOGGER = logging.getLogger(__name__)
_ACTIVE_API_APP: ContextVar[FastAPI | None] = ContextVar("orket_active_api_app", default=None)
_PayloadT = TypeVar("_PayloadT")


def _resolve_default_project_root() -> Path:
    return Path(__file__).parents[2]


def _current_api_app(target_app: FastAPI | None = None) -> FastAPI:
    if target_app is not None:
        return target_app
    active_app = _ACTIVE_API_APP.get()
    if active_app is not None:
        return active_app
    raise RuntimeError("No API app is active. Use create_api_app() and pass or enter that app context.")


def _configured_project_root(target_app: FastAPI | None = None) -> Path:
    root = getattr(_current_api_app(target_app).state, "project_root", None)
    if root is None:
        raise RuntimeError("API project root is not initialized. Call create_api_app() first.")
    return Path(root).resolve()


def _project_root(target_app: FastAPI | None = None) -> Path:
    return Path(_runtime_context(target_app).project_root)


def _resolve_method(target: object, invocation: dict[str, Any], error_prefix: str) -> Callable[..., Any]:
    method_name = invocation["method_name"]
    method = getattr(target, method_name, None)
    if method is None or not callable(method):
        detail = invocation.get("unsupported_detail")
        if detail:
            raise HTTPException(status_code=400, detail=detail)
        raise HTTPException(status_code=400, detail=f"Unsupported {error_prefix} method '{method_name}'.")
    return cast(Callable[..., Any], method)


async def _invoke_async_method(target: object, invocation: dict[str, Any], error_prefix: str) -> Any:
    invocation = api_policy.capture_api_invocation(invocation)
    method = _resolve_method(target, invocation, error_prefix)
    return await method(*invocation.get("args", []), **invocation.get("kwargs", {}))


async def _schedule_async_invocation_task(
    target: object,
    invocation: dict[str, Any],
    error_prefix: str,
    session_id: str,
) -> None:
    invocation = api_policy.capture_api_invocation(invocation)
    method = _resolve_method(target, invocation, error_prefix)
    task = asyncio.create_task(method(*invocation.get("args", []), **invocation.get("kwargs", {})))
    context = _runtime_context()
    state = _get_runtime_state()
    context.track_background_task(task)
    await state.add_task(session_id, task)
    loop = asyncio.get_running_loop()

    # Always remove completed/canceled tasks to keep active task tracking accurate.
    def _cleanup(_done_task: asyncio.Task[Any]) -> None:
        async def _release_task() -> None:
            await state.remove_task(session_id, task)
            context.release_background_task(task)

        def _start_cleanup() -> None:
            if not context.accepting_work:
                return
            cleanup_task = asyncio.create_task(_release_task())
            context.track_background_task(cleanup_task)
            cleanup_task.add_done_callback(context.release_background_task)

        with suppress(RuntimeError):
            loop.call_soon_threadsafe(_start_cleanup)

    task.add_done_callback(_cleanup)


def _runtime_task_summary(tasks: list[asyncio.Task[Any]]) -> tuple[bool, str]:
    active_tasks = [task for task in tasks if not task.done()]
    if active_tasks:
        return True, "running"
    if any(task.done() and not task.cancelled() for task in tasks):
        return False, "completed"
    if any(task.cancelled() for task in tasks):
        return False, "canceled"
    return False, "idle"


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


def _parse_roles_filter(roles: str | None) -> list[str]:
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
            for role_name in declared_roles:
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

        raw_declared_roles = payload.get("roles")
        declared_roles: dict[str, Any] = dict(raw_declared_roles) if isinstance(raw_declared_roles, dict) else {}
        role_items: list[dict[str, Any]] = []
        all_roles = sorted(
            set(referenced_roles)
            | {_normalize_role_name(role) for role in declared_roles if _normalize_role_name(role)}
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


async def _log_api_auth_rejection(
    *,
    request_path: str,
    reason: str,
    provided_key_present: bool,
) -> None:
    await _runtime_context().events.emit(
        "api_auth_rejected",
        {
            "route_class": "core",
            "reason": reason,
            "request_path": request_path,
            "provided_key_present": provided_key_present,
        },
    )


def _api_key_actor_ref(api_key_value: str | None) -> str | None:
    token = str(api_key_value or "").strip()
    if not token:
        return None
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"api_key_fingerprint:sha256:{digest}"


async def get_api_key(request: Request, api_key_header: str | None = Security(api_key_header)) -> str | None:
    request_path = str(request.url.path or "")
    provided_key_present = bool(str(api_key_header or "").strip())

    if _runtime_context().authentication.authenticate(api_key_header):
        request.state.authenticated_actor_ref = _api_key_actor_ref(api_key_header)
        return api_key_header

    await _log_api_auth_rejection(
        request_path=request_path,
        reason="invalid_or_missing_key_for_core_route",
        provided_key_present=provided_key_present,
    )

    raise HTTPException(
        status_code=403,
        detail="Could not validate credentials",
    )


# --- Lifespan ---


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with _app.state.api_preparation.open() as prepared:
        context = set_api_runtime_context(_app, prepared.container)
        _app.state.outbound_policy_config = prepared.outbound_policy
        state, runtime_node = context.runtime_state, context.api_runtime_node
        async with api_runtime_lifespan(context, context.project_root, lambda: event_broadcaster(state, runtime_node)):
            _app.state.api_ready = True
            try:
                yield
            finally:
                _app.state.api_ready = False


def _filter_operator_payload(payload: _PayloadT, *, surface: str) -> _PayloadT:
    base_config = dict(getattr(_current_api_app().state, "outbound_policy_config", {}) or {})
    filtered, _report = apply_outbound_policy_gate(
        payload,
        merge_outbound_policy_config(base_config, {"surface": surface}),
    )
    return cast(_PayloadT, filtered)


# Apply auth to all v1 endpoints if configured
v1_router = APIRouter(prefix="/v1", dependencies=[Depends(get_api_key)])

def _runtime_context(target_app: FastAPI | None = None) -> ApiAppRuntimeContext:
    selected_app = _current_api_app(target_app)
    root = _configured_project_root(selected_app)
    context = get_api_runtime_context(selected_app)
    if context is None or context.project_root != root:
        raise RuntimeError("API app runtime context does not match its configured project root.")
    if not context.accepting_work:
        raise RuntimeError("API app runtime context is closed.")
    return context


def _get_api_runtime_node(target_app: FastAPI | None = None) -> Any:
    return _runtime_context(target_app).api_runtime_node


def _get_runtime_state(target_app: FastAPI | None = None) -> Any:
    return _runtime_context(target_app).runtime_state


def _get_api_runtime_host(target_app: FastAPI | None = None) -> ApiRuntimeHostService:
    return _runtime_context(target_app).api_runtime_host


def _get_engine(target_app: FastAPI | None = None) -> Any:
    return _runtime_context(target_app).engine


def _get_interaction_manager(target_app: FastAPI | None = None) -> InteractionManager:
    return cast(InteractionManager, _runtime_context(target_app).interaction_manager)


def _get_extension_manager(target_app: FastAPI | None = None) -> Any:
    return _runtime_context(target_app).extension_manager


def _get_extension_runtime_service(target_app: FastAPI | None = None) -> Any:
    return _runtime_context(target_app).extension_runtime_service


def _get_outward_run_service() -> Any:
    return _runtime_context().outward_run_service


def _get_outward_approval_service() -> Any:
    return _runtime_context().outward_approval_service


def _get_outward_run_execution_service() -> Any:
    return _runtime_context().outward_run_execution_service


def _get_outward_run_inspection_service() -> Any:
    return _runtime_context().outward_run_inspection_service


def _get_outward_ledger_service() -> Any:
    return _runtime_context().outward_ledger_service


def _get_governed_agent_runtime() -> Any:
    runtime = _runtime_context().governed_agent_runtime
    if runtime is None:
        raise RuntimeError("Governed-agent runtime is unavailable.")
    return runtime


# --- System Endpoints ---


async def health() -> dict[str, str]:
    return {"status": "ok"}


# --- v1 Endpoints ---


@v1_router.get("/version")
async def get_version() -> dict[str, str]:
    return _filter_operator_payload({"version": __version__, "api": "v1"}, surface="api.version")


v1_router.include_router(
    build_kernel_router(
        lambda: _get_engine(),
        outward_approval_service_getter=lambda: _get_outward_approval_service(),
        outward_execution_service_getter=lambda: _get_outward_run_execution_service(),
        outbound_filter=lambda payload, surface: _filter_operator_payload(payload, surface=surface),
    )
)
v1_router.include_router(build_cards_router(lambda: _get_engine(), lambda: _get_api_runtime_node()))
v1_router.include_router(build_card_authoring_router(lambda: _get_engine(), lambda: _project_root()))
v1_router.include_router(
    build_flows_router(
        engine_getter=lambda: _get_engine(),
        host_getter=lambda: _get_api_runtime_host(),
        schedule_async_invocation_task=_schedule_async_invocation_task,
    )
)
v1_router.include_router(build_runs_router(lambda: _get_engine(), outward_execution_service_getter=lambda: _get_outward_run_execution_service(), outbound_filter=lambda payload, surface: _filter_operator_payload(payload, surface=surface)))
v1_router.include_router(build_outward_ledger_router(
    service_getter=lambda: _get_outward_ledger_service(),
    outbound_filter=lambda payload, surface: _filter_operator_payload(payload, surface=surface),
))
v1_router.include_router(
    build_settings_router(
        settings_order=SETTINGS_ORDER,
        settings_schema=SETTINGS_SCHEMA,
        runtime_policy_options=lambda: runtime_policy_options(),
        load_user_settings=lambda: load_user_settings_async(),
        save_user_settings=lambda settings, **options: save_user_settings_async(settings, **options),
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
        project_root_getter=lambda: _project_root(),
        runtime_state=lambda: _get_runtime_state(),
        api_runtime_node_getter=lambda: _get_api_runtime_node(),
        system_queries_getter=lambda: _runtime_context().system_queries,
        runtime_host_getter=lambda: _get_api_runtime_host(),
        now_local=lambda: _runtime_context().system_queries.local_now(),
        events_getter=lambda: _runtime_context().events,
        model_selection_getter=lambda: _runtime_context().model_selection,
        parse_roles_filter=lambda roles: _parse_roles_filter(roles),
        discover_active_roles=lambda root: _discover_active_roles(root),
        discover_team_topology=lambda root: _discover_team_topology(root),
        invoke_async_method=_invoke_async_method,
        schedule_async_invocation_task=_schedule_async_invocation_task,
        engine_getter=lambda: _get_engine(),
    )
)
v1_router.include_router(
    build_sessions_router(
        turn_service_getter=lambda: _runtime_context().interactions(),
        workspace_root_getter=lambda: _project_root(),
        cancellation_service_getter=lambda: _runtime_context().interaction_cancellation(),
    )
)
v1_router.include_router(build_extension_runtime_router(service_getter=lambda: _get_extension_runtime_service()))
v1_router.include_router(
    build_governed_agents_router(
        runtime_getter=lambda: _get_governed_agent_runtime(),
        outbound_filter=lambda payload, surface: _filter_operator_payload(payload, surface=surface),
    )
)


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
    runtime_engine = _get_engine()
    if runtime_engine.org and isinstance(getattr(runtime_engine.org, "process_rules", None), dict):
        return dict(runtime_engine.org.process_rules)
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


_RUN_SUBMISSION_BODY = Body(...)


@v1_router.post("/runs")
async def submit_run(payload: dict[str, Any] = _RUN_SUBMISSION_BODY) -> dict[str, Any]:
    try:
        record = await _get_outward_run_service().submit(payload)
        record = await _get_outward_run_execution_service().start_if_ready(record.run_id)
    except OutwardRunValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OutwardRunExecutionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OutwardRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _filter_operator_payload(await _get_outward_run_service().status_payload(record.run_id), surface="api.runs.submit")


@v1_router.get("/runs")
async def list_runs(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    records = await _get_outward_run_service().list_runs(status=status, limit=limit, offset=offset)
    if records or status is not None or limit != 20 or offset != 0:
        payload = {
            "items": [await _get_outward_run_service().status_payload(record.run_id) for record in records],
            "count": len(records),
            "limit": limit,
            "offset": offset,
            "filters": {"status": status},
        }
        return _filter_operator_payload(payload, surface="api.runs.list")
    invocation = _get_api_runtime_node().resolve_runs_invocation()
    runtime_engine = _get_engine()
    payload = await _invoke_async_method(runtime_engine.sessions, invocation, "runs")
    return _filter_operator_payload(payload, surface="api.runs.list")


def _parse_event_types(types: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(types or "").split(",") if item.strip())


@v1_router.get("/runs/{run_id}/events")
async def get_outward_run_events(
    run_id: str,
    from_turn: int | None = Query(default=None, ge=0),
    to_turn: int | None = Query(default=None, ge=0),
    types: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict[str, Any]:
    try:
        payload = await _get_outward_run_inspection_service().events(
            run_id,
            from_turn=from_turn,
            to_turn=to_turn,
            types=_parse_event_types(types),
            agent_id=agent_id,
            limit=limit,
        )
    except OutwardRunInspectionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _filter_operator_payload(payload, surface="api.runs.events")


@v1_router.get("/runs/{run_id}/summary")
async def get_outward_run_summary(run_id: str) -> dict[str, Any]:
    try:
        payload = await _get_outward_run_inspection_service().summary(run_id)
    except OutwardRunInspectionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _filter_operator_payload(payload, surface="api.runs.summary")


@v1_router.get("/runs/{run_id}/events/stream")
async def stream_outward_run_events(
    run_id: str,
    types: str | None = Query(default=None),
) -> StreamingResponse:
    if await _get_outward_run_service().get_status(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    async def _stream() -> AsyncIterator[str]:
        seen: set[str] = set()
        event_types = _parse_event_types(types)
        while True:
            payload = await _get_outward_run_inspection_service().events(run_id, types=event_types)
            emitted = False
            for event in payload["events"]:
                event_id = str(event.get("event_id") or "")
                if event_id in seen:
                    continue
                seen.add(event_id)
                filtered = _filter_operator_payload(event, surface="api.runs.events.stream")
                yield f"event: run_event\ndata: {json.dumps(filtered, sort_keys=True)}\n\n"
                emitted = True
            run = await _get_outward_run_service().get_status(run_id)
            if run is None or run.status in {"completed", "failed"}:
                break
            if not emitted:
                yield "event: heartbeat\ndata: {}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(_stream(), media_type="text/event-stream")


@v1_router.get("/runs/{session_id}")
async def get_run_detail(session_id: str) -> dict[str, Any]:
    outward_record = await _get_outward_run_service().get_status(session_id)
    if outward_record is not None:
        return _filter_operator_payload(await _get_outward_run_service().status_payload(outward_record.run_id), surface="api.runs.status")

    runtime_engine = _get_engine()
    run_record = await runtime_engine.run_ledger.get_run(session_id)
    session = await runtime_engine.sessions.get_session(session_id)

    if run_record is None and session is None:
        raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")

    backlog = await runtime_engine.sessions.get_session_issues(session_id)
    summary = {}
    artifacts = {}
    status = None
    projected_run_record = validated_run_ledger_record_projection(run_record)
    if isinstance(projected_run_record, dict):
        summary = dict(projected_run_record.get("summary_json") or {})
        artifacts = dict(projected_run_record.get("artifact_json") or {})
        status = projected_run_record.get("status")
    if status is None and isinstance(session, dict):
        status = session.get("status")

    payload = {
        "session_id": session_id,
        "status": status,
        "summary": summary,
        "artifacts": artifacts,
        "issue_count": len(backlog),
        "session": session,
        "run_ledger": projected_run_record,
    }
    return _filter_operator_payload(payload, surface="api.runs.status")


@v1_router.get("/runs/{session_id}/metrics")
async def get_run_metrics(session_id: str) -> Any:
    await _runtime_context().events.emit("api_run_metrics", {"session_id": session_id})
    metrics_reader = _get_api_runtime_host().create_member_metrics_reader()
    try:
        return await _runtime_context().system_queries.member_metrics(session_id, metrics_reader)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail="Invalid session_id") from exc


@v1_router.get("/runs/{session_id}/token-summary")
async def get_run_token_summary(session_id: str) -> dict[str, Any]:
    runtime_engine = _get_engine()
    run_record = await runtime_engine.run_ledger.get_run(session_id)
    session = await runtime_engine.sessions.get_session(session_id)
    if run_record is None and session is None:
        raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")

    try:
        return await _runtime_context().run_queries.token_summary(session_id)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@v1_router.get("/runs/{session_id}/replay")
async def list_run_replay_turns(session_id: str, role: str | None = None) -> dict[str, Any]:
    runtime_engine = _get_engine()
    run_record = await runtime_engine.run_ledger.get_run(session_id)
    session = await runtime_engine.sessions.get_session(session_id)
    if run_record is None and session is None:
        raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")
    try:
        turns = await _runtime_context().run_queries.replay_turns(session_id, role)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "session_id": session_id,
        "turn_count": len(turns),
        "filters": {"role": role or None},
        "turns": turns,
    }


@v1_router.get("/runs/{session_id}/backlog")
async def get_backlog(session_id: str) -> Any:
    await _runtime_context().events.emit("api_backlog", {"session_id": session_id})
    invocation = _get_api_runtime_node().resolve_backlog_invocation(session_id)
    runtime_engine = _get_engine()
    return await _invoke_async_method(runtime_engine.sessions, invocation, "backlog")


@v1_router.get("/runs/{session_id}/execution-graph")
async def get_execution_graph(session_id: str) -> dict[str, Any]:
    runtime_engine = _get_engine()
    run_record = await runtime_engine.run_ledger.get_run(session_id)
    session = await runtime_engine.sessions.get_session(session_id)
    if run_record is None and session is None:
        raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")

    graph = await inspect_execution_graph(cards=runtime_engine.cards, session_id=session_id)
    index = {node["id"]: node["order_index"] for node in graph["nodes"]}
    try:
        handoffs = await _runtime_context().run_queries.handoffs(session_id, index)
        run_path = await _runtime_context().run_queries.run_path(session_id)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = execution_graph_payload(session_id=session_id, graph=graph, handoffs=handoffs)
    await persist_execution_graph_snapshot(cards=runtime_engine.cards, run_path=run_path, payload=payload)
    return payload


@v1_router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str) -> Any:
    await _runtime_context().events.emit("api_session_detail", {"session_id": session_id})
    runtime_node = _get_api_runtime_node()
    invocation = runtime_node.resolve_session_detail_invocation(session_id)
    runtime_engine = _get_engine()
    session = await _invoke_async_method(runtime_engine.sessions, invocation, "session")
    if not session:
        interaction_session = await _get_interaction_manager().queries.get_session_detail(session_id)
        if interaction_session is not None:
            return interaction_session
        raise HTTPException(**runtime_node.session_detail_not_found_error(session_id))
    return session


@v1_router.get("/sessions/{session_id}/status")
async def get_session_status(session_id: str) -> dict[str, Any]:
    runtime_node = _get_api_runtime_node()
    runtime_engine = _get_engine()
    session = await runtime_engine.sessions.get_session(session_id)
    if not session:
        interaction_status = await _get_interaction_manager().queries.get_session_status(session_id)
        if interaction_status is not None:
            return cast(dict[str, Any], interaction_status)
        raise HTTPException(**runtime_node.session_detail_not_found_error(session_id))

    run_record = await runtime_engine.run_ledger.get_run(session_id)
    projected_run_record = validated_run_ledger_record_projection(run_record)
    backlog = await runtime_engine.sessions.get_session_issues(session_id)
    tasks = await _get_runtime_state().get_tasks(session_id)
    is_active, task_state = _runtime_task_summary(tasks)

    backlog_counts: dict[str, int] = {}
    for issue in backlog:
        issue_status = str(issue.get("status") or "unknown")
        backlog_counts[issue_status] = backlog_counts.get(issue_status, 0) + 1

    return {
        "session_id": session_id,
        "active": is_active,
        "status": (projected_run_record or {}).get("status", session.get("status")),
        "task_state": task_state,
        "backlog": {
            "count": len(backlog),
            "by_status": backlog_counts,
        },
        "summary": dict((projected_run_record or {}).get("summary_json") or {}),
        "artifacts": dict((projected_run_record or {}).get("artifact_json") or {}),
    }


@v1_router.post("/sessions/{session_id}/halt")
async def halt_session(session_id: str, request: Request) -> dict[str, Any]:
    runtime_engine = _get_engine()
    run_record = await runtime_engine.run_ledger.get_run(session_id)
    if run_record is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    await runtime_engine.halt_session(
        session_id,
        operator_actor_ref=getattr(request.state, "authenticated_actor_ref", None),
    )
    tasks = await _get_runtime_state().get_tasks(session_id)
    is_active, _task_state = _runtime_task_summary(tasks)
    return {
        "ok": True,
        "session_id": session_id,
        "active": is_active,
    }


@v1_router.get("/sessions/{session_id}/replay")
async def replay_session_turn(
    session_id: str,
    issue_id: str | None = None,
    turn_index: int | None = Query(default=None, ge=1),
    role: str | None = None,
) -> Any:
    runtime_engine = _get_engine()
    run_record = await runtime_engine.run_ledger.get_run(session_id)
    session = await runtime_engine.sessions.get_session(session_id)
    if not issue_id and turn_index is None:
        if run_record is None and session is None:
            interaction_timeline = await _get_interaction_manager().queries.get_session_replay_timeline(
                session_id,
                role=role,
            )
            if interaction_timeline is not None:
                return interaction_timeline
            raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")
        return await list_run_replay_turns(session_id=session_id, role=role)
    if not issue_id or turn_index is None:
        raise HTTPException(
            status_code=422,
            detail="Both 'issue_id' and 'turn_index' are required for targeted replay.",
        )
    if run_record is None and session is None:
        interaction_session = await _get_interaction_manager().queries.get_session_detail(session_id)
        if interaction_session is not None:
            raise HTTPException(
                status_code=422,
                detail="Targeted replay is not supported for interaction sessions.",
            )
    try:
        replay = await read_runtime_replay(
            runtime_engine,
            session_id=session_id,
            issue_id=str(issue_id),
            turn_index=turn_index,
            role=role,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return replay


@v1_router.get("/sessions/{session_id}/snapshot")
async def get_session_snapshot(session_id: str) -> Any:
    await _runtime_context().events.emit("api_session_snapshot", {"session_id": session_id})
    runtime_node = _get_api_runtime_node()
    invocation = runtime_node.resolve_session_snapshot_invocation(session_id)
    runtime_engine = _get_engine()
    snapshot = await _invoke_async_method(runtime_engine.snapshots, invocation, "snapshot")
    if not snapshot:
        interaction_snapshot = await _get_interaction_manager().queries.get_session_snapshot(session_id)
        if interaction_snapshot is not None:
            return interaction_snapshot
        raise HTTPException(**runtime_node.session_snapshot_not_found_error(session_id))
    return snapshot


@v1_router.get("/sandboxes")
async def list_sandboxes() -> Any:
    invocation = _get_api_runtime_node().resolve_sandboxes_list_invocation()
    runtime_engine = _get_engine()
    return await _invoke_async_method(runtime_engine, invocation, "sandboxes")


@v1_router.post("/sandboxes/{sandbox_id}/stop")
async def stop_sandbox(sandbox_id: str, request: Request) -> dict[str, bool]:
    invocation = _get_api_runtime_node().resolve_sandbox_stop_invocation(sandbox_id)
    operator_actor_ref = getattr(request.state, "authenticated_actor_ref", None)
    if operator_actor_ref is not None:
        invocation = {
            **invocation,
            "kwargs": {
                **dict(invocation.get("kwargs", {})),
                "operator_actor_ref": operator_actor_ref,
            },
        }
    try:
        runtime_engine = _get_engine()
        await _invoke_async_method(runtime_engine, invocation, "sandbox stop")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@v1_router.get("/sandboxes/{sandbox_id}/logs")
async def get_sandbox_logs(sandbox_id: str, service: str | None = None) -> dict[str, Any]:
    runtime_node = _get_api_runtime_node()
    construct = partial(_get_api_runtime_host().create_execution_pipeline,
                        runtime_node.resolve_sandbox_workspace(_project_root()))
    invocation = api_policy.capture_api_invocation(runtime_node.resolve_sandbox_logs_invocation(sandbox_id, service))
    async with open_runtime_owner(construct, label="api-sandbox-log-construction") as pipeline:
        method = _resolve_method(pipeline.sandbox_orchestrator, invocation, "sandbox logs")
        read = partial(method, *invocation.get("args", []), **invocation.get("kwargs", {}))
        return {"logs": await read_runtime_sandbox_logs(read)}


def _coerce_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: '{value}'") from exc


@v1_router.get("/logs")
async def list_logs(
    session_id: str | None = None,
    event: str | None = None,
    role: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    start_dt = _coerce_datetime(start_time)
    end_dt = _coerce_datetime(end_time)

    try:
        page = await _runtime_context().run_queries.logs(
            session_id=session_id, event=event, role=role, start_dt=start_dt, end_dt=end_dt,
            limit=limit, offset=offset,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**page, "filters": {"session_id": session_id, "event": event, "role": role,
                               "start_time": start_time, "end_time": end_time}}


async def event_broadcaster(state: Any, runtime_node: Any) -> None:
    while True:
        record = await state.event_queue.get()
        try:
            for ws in await state.get_websockets():
                try:
                    await ws.send_json(record)
                except (WebSocketDisconnect, RuntimeError, ValueError) as exc:
                    if isinstance(exc, WebSocketDisconnect) or api_policy.recommend_websocket_removal(runtime_node, exc):
                        await state.remove_websocket(ws)
        finally:
            state.event_queue.task_done()


def create_api_app(
    project_root: Path | None = None, *, runtime_inputs: Any | None = None,
    environment: Mapping[str, str] | None = None,
) -> FastAPI:
    inputs = RuntimeConstructionInputs.capture(environment=environment)
    root = inputs.invocation_root / (project_root if project_root is not None else _resolve_default_project_root())
    created_app = FastAPI(title="Orket API", version=__version__, lifespan=lifespan)
    created_app.state.project_root = root
    created_app.state.api_ready = False
    created_app.state.api_preparation = build_api_runtime_preparation(root, inputs=inputs, runtime_inputs=runtime_inputs)
    register_api_transport(created_app, environment=inputs.environment, active_app=_ACTIVE_API_APP,
        router=v1_router, health=health, api_key_name=API_KEY_NAME,
        authentication_getter=lambda: _runtime_context(created_app).authentication,
        runtime_host_getter=lambda: _get_api_runtime_host(created_app),
        interaction_manager_getter=lambda: _get_interaction_manager(created_app),
        runtime_state_getter=lambda: _get_runtime_state(created_app),
        events_getter=lambda: _runtime_context(created_app).events)
    return created_app
