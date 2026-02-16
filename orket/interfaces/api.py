import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, APIRouter, Depends, Security, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
import os

from orket import __version__
from orket.logging import subscribe_to_events, log_event
from orket.state import runtime_state
from orket.hardware import get_metrics_snapshot
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.time_utils import now_local
from orket.settings import load_user_settings, save_user_settings
from orket.orchestration.models import ModelSelector
from orket.application.services.runtime_policy import (
    allowed_architecture_patterns,
    is_microservices_pilot_stable,
    is_microservices_unlocked,
    resolve_architecture_mode,
    resolve_frontend_framework_mode,
    resolve_gitea_state_pilot_enabled,
    resolve_project_surface_profile,
    resolve_small_project_builder_variant,
    resolve_state_backend_mode,
    runtime_policy_options,
)


from pydantic import BaseModel

api_runtime_node = DecisionNodeRegistry().resolve_api_runtime()


def _resolve_async_method(target: object, invocation: dict, error_prefix: str):
    method_name = invocation["method_name"]
    method = getattr(target, method_name, None)
    if method is None:
        detail = invocation.get("unsupported_detail")
        if detail:
            raise HTTPException(status_code=400, detail=detail)
        raise HTTPException(status_code=400, detail=f"Unsupported {error_prefix} method '{method_name}'.")
    return method


def _resolve_sync_method(target: object, invocation: dict, error_prefix: str):
    method_name = invocation["method_name"]
    method = getattr(target, method_name, None)
    if method is None:
        detail = invocation.get("unsupported_detail")
        if detail:
            raise HTTPException(status_code=400, detail=detail)
        raise HTTPException(status_code=400, detail=f"Unsupported {error_prefix} method '{method_name}'.")
    return method


async def _invoke_async_method(target: object, invocation: dict, error_prefix: str):
    method = _resolve_async_method(target, invocation, error_prefix)
    return await method(*invocation.get("args", []), **invocation.get("kwargs", {}))


async def _schedule_async_invocation_task(
    target: object,
    invocation: dict,
    error_prefix: str,
    session_id: str,
):
    method = _resolve_async_method(target, invocation, error_prefix)
    task = asyncio.create_task(method(*invocation.get("args", []), **invocation.get("kwargs", {})))
    await runtime_state.add_task(session_id, task)

    # Always remove completed/canceled tasks to keep active task tracking accurate.
    def _cleanup(_done_task: asyncio.Task):
        asyncio.create_task(runtime_state.remove_task(session_id))

    task.add_done_callback(_cleanup)


def _invoke_sync_method(target: object, invocation: dict, error_prefix: str):
    method = _resolve_sync_method(target, invocation, error_prefix)
    return method(*invocation.get("args", []), **invocation.get("kwargs", {}))

class SaveFileRequest(BaseModel):
    path: str
    content: str

class RunAssetRequest(BaseModel):
    path: Optional[str] = None
    build_id: Optional[str] = None
    type: Optional[str] = None
    issue_id: Optional[str] = None

class ChatDriverRequest(BaseModel):
    message: str

class ArchiveCardsRequest(BaseModel):
    card_ids: Optional[list[str]] = None
    build_id: Optional[str] = None
    related_tokens: Optional[list[str]] = None
    reason: Optional[str] = None
    archived_by: Optional[str] = "api"


class RuntimePolicyUpdateRequest(BaseModel):
    architecture_mode: Optional[str] = None
    frontend_framework_mode: Optional[str] = None
    project_surface_profile: Optional[str] = None
    small_project_builder_variant: Optional[str] = None
    state_backend_mode: Optional[str] = None
    gitea_state_pilot_enabled: Optional[bool] = None


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

# Security dependency
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    expected_key = os.getenv("ORKET_API_KEY")
    if not api_runtime_node.is_api_key_valid(expected_key, api_key_header):
        raise HTTPException(
            status_code=403,
            detail=api_runtime_node.api_key_invalid_detail(),
        )
    return api_key_header

# --- Lifespan ---

def _on_log_record_factory(loop: asyncio.AbstractEventLoop):
    def on_log_record(record):
        loop.call_soon_threadsafe(runtime_state.event_queue.put_nowait, record)
    return on_log_record


@asynccontextmanager
async def lifespan(_app: FastAPI):
    broadcaster_task = asyncio.create_task(event_broadcaster())
    loop = asyncio.get_running_loop()
    subscribe_to_events(_on_log_record_factory(loop))
    expected_key = os.getenv("ORKET_API_KEY", "").strip()
    insecure_bypass = os.getenv("ORKET_ALLOW_INSECURE_NO_API_KEY", "").strip().lower() in {"1", "true", "yes", "on"}
    log_event(
        "api_security_posture",
        {
            "api_key_configured": bool(expected_key),
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
        broadcaster_task.cancel()
        try:
            await broadcaster_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Orket API", version=__version__, lifespan=lifespan)
# Apply auth to all v1 endpoints if configured
v1_router = APIRouter(prefix="/v1", dependencies=[Depends(get_api_key)])

origins_str = os.getenv("ORKET_ALLOWED_ORIGINS", api_runtime_node.default_allowed_origins_value())
origins = api_runtime_node.parse_allowed_origins(origins_str)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
engine = api_runtime_node.create_engine(api_runtime_node.resolve_api_workspace(PROJECT_ROOT))

# --- System Endpoints ---

@app.get("/health")
async def health(): return {"status": "ok", "organization": "Orket"}

# --- v1 Endpoints ---

@v1_router.get("/version")
async def get_version():
    return {"version": __version__, "api": "v1"}

@v1_router.post("/system/clear-logs")
async def clear_logs():
    log_path = api_runtime_node.resolve_clear_logs_path()
    fs = api_runtime_node.create_file_tools(PROJECT_ROOT)
    try:
        invocation = api_runtime_node.resolve_clear_logs_invocation(log_path)
        await _invoke_async_method(fs, invocation, "clear logs")
    except (PermissionError, FileNotFoundError, OSError) as exc:
        log_event(
            "clear_logs_skipped",
            {"path": log_path, "error": str(exc)},
            PROJECT_ROOT,
        )
    return {"ok": True}

@v1_router.get("/system/heartbeat")
async def heartbeat():
    return {
        "status": "online",
        "timestamp": now_local().isoformat(),
        "active_tasks": len(runtime_state.active_tasks)  # Read-only len() is safe without lock
    }

@v1_router.get("/system/metrics")
async def get_metrics():
    return api_runtime_node.normalize_metrics(get_metrics_snapshot())

@v1_router.get("/system/explorer")
async def list_system_files(path: str = "."):
    target = api_runtime_node.resolve_explorer_path(PROJECT_ROOT, path)
    if target is None:
        raise HTTPException(**api_runtime_node.resolve_explorer_forbidden_error(path))
    if not target.exists():
        return api_runtime_node.resolve_explorer_missing_response(path)
    
    items = []
    for p in target.iterdir():
        if not api_runtime_node.include_explorer_entry(p.name):
            continue
        is_dir = p.is_dir()
        items.append({"name": p.name, "is_dir": is_dir, "ext": p.suffix})
    return {"items": api_runtime_node.sort_explorer_items(items), "path": path}

@v1_router.get("/system/read")
async def read_system_file(path: str):
    fs = api_runtime_node.create_file_tools(PROJECT_ROOT)
    try:
        invocation = api_runtime_node.resolve_read_invocation(path)
        content = await _invoke_async_method(fs, invocation, "read")
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=api_runtime_node.permission_denied_detail("read", str(exc)),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=api_runtime_node.read_not_found_detail(path)) from exc
    return {"content": content}

@v1_router.post("/system/save")
async def save_system_file(req: SaveFileRequest):
    fs = api_runtime_node.create_file_tools(PROJECT_ROOT)
    try:
        invocation = api_runtime_node.resolve_save_invocation(req.path, req.content)
        await _invoke_async_method(fs, invocation, "save")
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=api_runtime_node.permission_denied_detail("save", str(exc)),
        ) from exc
    return {"ok": True}

@v1_router.get("/system/calendar")
async def get_calendar():
    now = now_local()
    calendar_window = api_runtime_node.calendar_window(now)
    return {
        "current_sprint": api_runtime_node.resolve_current_sprint(now),
        "sprint_start": calendar_window["sprint_start"],
        "sprint_end": calendar_window["sprint_end"],
    }


@v1_router.get("/system/runtime-policy/options")
async def get_runtime_policy_options():
    return runtime_policy_options()


@v1_router.get("/system/model-assignments")
async def get_model_assignments(roles: Optional[str] = None):
    role_filter = _parse_roles_filter(roles)
    active_roles = role_filter or _discover_active_roles(PROJECT_ROOT / "model")
    selector = ModelSelector(organization=engine.org, user_settings=load_user_settings())

    items: list[dict[str, Any]] = []
    for role in active_roles:
        selected_model = selector.select(role=role)
        decision = selector.get_last_selection_decision()
        final_model = str(decision.get("final_model") or selected_model)
        items.append(
            {
                "role": role,
                "selected_model": str(decision.get("selected_model") or selected_model),
                "final_model": final_model,
                "demoted": bool(decision.get("demoted", False)),
                "reason": str(decision.get("reason") or "unknown"),
                "dialect": selector.get_dialect_name(final_model),
            }
        )
    return {
        "items": items,
        "count": len(items),
        "generated_at": now_local().isoformat(),
        "filters": {"roles": role_filter or None},
    }


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
        if _parse_setting_value(field, env_value) is not None:
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


@v1_router.get("/settings")
async def get_settings():
    user_settings = load_user_settings()
    process_rules = _runtime_policy_process_rules()
    return {"settings": _resolve_settings_snapshot(user_settings, process_rules)}


@v1_router.patch("/settings")
async def update_settings(payload: dict[str, Any] = Body(...)):
    editable = {key: payload[key] for key in SETTINGS_ORDER if key in payload}
    errors: list[dict[str, Any]] = []
    for key in payload.keys():
        if key not in SETTINGS_SCHEMA:
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
        parsed = _parse_setting_value(field, raw_value)
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
    process_rules = _runtime_policy_process_rules()
    candidate = user_settings.copy()
    candidate.update(normalized)
    snapshot = _resolve_settings_snapshot(candidate, process_rules)
    if snapshot["state_backend_mode"]["value"] == "gitea" and not snapshot["gitea_state_pilot_enabled"]["value"]:
        errors.append(
            {
                "field": "state_backend_mode",
                "code": "policy_guard",
                "message": "state_backend_mode='gitea' requires gitea_state_pilot_enabled=true.",
            }
        )

    if errors:
        raise _settings_validation_error(errors)

    user_settings.update(normalized)
    save_user_settings(user_settings)
    return {
        "ok": True,
        "saved": normalized,
        "settings": _resolve_settings_snapshot(user_settings, process_rules),
    }


@v1_router.get("/system/runtime-policy")
async def get_runtime_policy():
    user_settings = load_user_settings()
    process_rules = _runtime_policy_process_rules()

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


@v1_router.post("/system/runtime-policy")
async def update_runtime_policy(req: RuntimePolicyUpdateRequest):
    current = load_user_settings().copy()
    if req.architecture_mode is not None:
        current["architecture_mode"] = resolve_architecture_mode(req.architecture_mode)
    if req.frontend_framework_mode is not None:
        current["frontend_framework_mode"] = resolve_frontend_framework_mode(req.frontend_framework_mode)
    if req.project_surface_profile is not None:
        current["project_surface_profile"] = resolve_project_surface_profile(req.project_surface_profile)
    if req.small_project_builder_variant is not None:
        current["small_project_builder_variant"] = resolve_small_project_builder_variant(
            req.small_project_builder_variant
        )
    if req.state_backend_mode is not None:
        current["state_backend_mode"] = resolve_state_backend_mode(req.state_backend_mode)
    if req.gitea_state_pilot_enabled is not None:
        current["gitea_state_pilot_enabled"] = bool(
            resolve_gitea_state_pilot_enabled(req.gitea_state_pilot_enabled)
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

@v1_router.post("/system/run-active")
async def run_active_asset(req: RunAssetRequest):
    session_id = api_runtime_node.create_session_id()

    asset_id = api_runtime_node.resolve_asset_id(req.path, req.issue_id)
    if not asset_id:
        raise HTTPException(
            status_code=400,
            detail=api_runtime_node.run_active_missing_asset_detail(),
        )

    invocation = api_runtime_node.resolve_run_active_invocation(
        asset_id=asset_id,
        build_id=req.build_id,
        session_id=session_id,
        request_type=req.type,
    )
    method_name = invocation["method_name"]

    log_event(
        "api_run_active",
        {
            "asset_id": asset_id,
            "request_type": req.type,
            "session_id": session_id,
            "method_name": method_name,
        },
        PROJECT_ROOT,
    )
    await _schedule_async_invocation_task(engine, invocation, "run", session_id)
    return {"session_id": session_id}

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
    workspace = api_runtime_node.resolve_member_metrics_workspace(PROJECT_ROOT, session_id)
    metrics_reader = api_runtime_node.create_member_metrics_reader()
    return metrics_reader(workspace)

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
    graph = _build_execution_graph(backlog)
    return {
        "session_id": session_id,
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        **graph,
    }

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
            else ("completed" if task and task.done() and not task.cancelled() else ("canceled" if task and task.cancelled() else "idle"))
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
    issue_id: str,
    turn_index: int = Query(ge=1),
    role: Optional[str] = None,
):
    try:
        replay = engine.replay_turn(
            session_id=session_id,
            issue_id=issue_id,
            turn_index=turn_index,
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
    await _invoke_async_method(engine, invocation, "sandbox stop")
    return {"ok": True}

@v1_router.get("/sandboxes/{sandbox_id}/logs")
async def get_sandbox_logs(sandbox_id: str, service: Optional[str] = None):
    pipeline = api_runtime_node.create_execution_pipeline(
        api_runtime_node.resolve_sandbox_workspace(PROJECT_ROOT)
    )
    invocation = api_runtime_node.resolve_sandbox_logs_invocation(sandbox_id, service)
    logs = _invoke_sync_method(pipeline.sandbox_orchestrator, invocation, "sandbox logs")
    return {"logs": logs}


def _coerce_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: '{value}'")


def _build_execution_graph(backlog: list[dict[str, Any]]) -> dict[str, Any]:
    items = [item for item in backlog if isinstance(item, dict)]
    index_by_id: dict[str, int] = {}
    status_by_id: dict[str, str] = {}
    for index, item in enumerate(items):
        issue_id = str(item.get("id") or "").strip()
        if not issue_id or issue_id in index_by_id:
            continue
        index_by_id[issue_id] = index
        status_by_id[issue_id] = str(item.get("status") or "unknown").strip().lower()

    edges: list[dict[str, str]] = []
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
            edges.append({"source": dep_id, "target": issue_id})
            adjacency[dep_id].append(issue_id)
            in_degree[issue_id] += 1

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
        candidate_files.append(PROJECT_ROOT / "workspace" / "runs" / session_id / "orket.log")

    records: list[dict] = []
    for path in candidate_files:
        records.extend(_read_log_records(path))

    def _record_session_id(record: dict) -> str:
        data = record.get("data", {})
        if isinstance(data, dict):
            runtime_event = data.get("runtime_event", {})
            if isinstance(runtime_event, dict):
                return str(runtime_event.get("session_id") or "")
            return str(data.get("session_id") or "")
        return ""

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


@v1_router.get("/cards")
async def list_cards(
    build_id: Optional[str] = None,
    session_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    cards = await engine.cards.list_cards(
        build_id=build_id,
        session_id=session_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "items": cards,
        "limit": limit,
        "offset": offset,
        "count": len(cards),
        "filters": {
            "build_id": build_id,
            "session_id": session_id,
            "status": status,
        },
    }


@v1_router.get("/cards/{card_id}")
async def get_card_detail(card_id: str):
    card = await engine.cards.get_by_id(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")
    if hasattr(card, "model_dump"):
        return card.model_dump()
    return card


@v1_router.get("/cards/{card_id}/history")
async def get_card_history(card_id: str):
    card = await engine.cards.get_by_id(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")
    history = await engine.cards.get_card_history(card_id)
    return {"card_id": card_id, "history": history}


@v1_router.get("/cards/{card_id}/comments")
async def get_card_comments(card_id: str):
    card = await engine.cards.get_by_id(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")
    comments = await engine.cards.get_comments(card_id)
    return {"card_id": card_id, "comments": comments}


@v1_router.get("/system/board")
async def get_system_board(dept: str = "core"):
    return api_runtime_node.resolve_system_board(dept)

@v1_router.get("/system/preview-asset")
async def preview_asset(path: str, issue_id: Optional[str] = None):
    target = api_runtime_node.resolve_preview_target(path, issue_id)
    invocation = api_runtime_node.resolve_preview_invocation(target, issue_id)
    builder = api_runtime_node.create_preview_builder(PROJECT_ROOT / "model")
    return await _invoke_async_method(builder, invocation, "preview")

@v1_router.post("/system/chat-driver")
async def chat_driver(req: ChatDriverRequest):
    driver = api_runtime_node.create_chat_driver()
    invocation = api_runtime_node.resolve_chat_driver_invocation(req.message)
    response = await _invoke_async_method(driver, invocation, "chat driver")
    return {"response": response}

@v1_router.post("/cards/archive")
async def archive_cards(req: ArchiveCardsRequest):
    if not api_runtime_node.has_archive_selector(req.card_ids, req.build_id, req.related_tokens):
        raise HTTPException(status_code=400, detail=api_runtime_node.archive_selector_missing_detail())

    archived_ids: list[str] = []
    missing_ids: list[str] = []
    archived_count = 0
    archived_by = req.archived_by or "api"

    if req.card_ids:
        result = await engine.archive_cards(req.card_ids, archived_by=archived_by, reason=req.reason)
        archived_ids.extend(result.get("archived", []))
        missing_ids.extend(result.get("missing", []))

    if req.build_id:
        count = await engine.archive_build(req.build_id, archived_by=archived_by, reason=req.reason)
        archived_count += count

    if req.related_tokens:
        result = await engine.archive_related_cards(req.related_tokens, archived_by=archived_by, reason=req.reason)
        archived_ids.extend(result.get("archived", []))
        missing_ids.extend(result.get("missing", []))

    return api_runtime_node.normalize_archive_response(
        archived_ids=archived_ids,
        missing_ids=missing_ids,
        archived_count=archived_count,
    )

app.include_router(v1_router)

# --- WS ---

async def event_broadcaster():
    while True:
        record = await runtime_state.event_queue.get()
        for ws in await runtime_state.get_websockets():
            try: await ws.send_json(record)
            except (WebSocketDisconnect, RuntimeError, ValueError) as exc:
                if isinstance(exc, WebSocketDisconnect) or api_runtime_node.should_remove_websocket(exc):
                    await runtime_state.remove_websocket(ws)
        runtime_state.event_queue.task_done()

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    expected_key = os.getenv("ORKET_API_KEY")
    header_key = websocket.headers.get(API_KEY_NAME) or websocket.headers.get(API_KEY_NAME.lower())
    query_key = websocket.query_params.get("api_key")
    supplied_key = header_key or query_key
    if not api_runtime_node.is_api_key_valid(expected_key, supplied_key):
        await websocket.close(code=4403)
        return
    await websocket.accept()
    await runtime_state.add_websocket(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        await runtime_state.remove_websocket(websocket)
