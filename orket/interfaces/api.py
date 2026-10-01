import hashlib
import logging
import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, TypeVar, cast

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Security, WebSocketDisconnect
from fastapi.security import APIKeyHeader

from orket import __version__
from orket.application.interactions.manager import InteractionManager
from orket.application.services import api_policy_input_service as api_policy
from orket.application.services.api_authentication_service import ApiAuthenticationService
from orket.application.services.api_runtime_host_service import ApiRuntimeHostService
from orket.application.services.api_runtime_preparation import build_api_runtime_preparation
from orket.application.services.api_startup_service import api_runtime_lifespan
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_policy_inputs import RuntimePolicySnapshot
from orket.interfaces.api_router_composition import register_api_domain_routes
from orket.interfaces.api_runtime_context import ApiAppRuntimeContext, get_api_runtime_context, set_api_runtime_context
from orket.interfaces.api_transport_composition import register_api_transport
from orket.kernel.v1.outbound_policy_gate import apply_outbound_policy_gate
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

    # Startup admission requires this owner before the app accepts requests.
    if cast(ApiAuthenticationService, _runtime_context().authentication).authenticate(api_key_header):
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
    filtered, _report = apply_outbound_policy_gate(
        payload,
        {"surface": surface},
        policy_inputs=_current_api_app().state.outbound_policy_config,
    )
    return cast(_PayloadT, filtered)


# Apply auth to all v1 endpoints if configured

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
    return cast(ApiRuntimeHostService, _runtime_context(target_app).api_runtime_host)


def _get_engine(target_app: FastAPI | None = None) -> Any:
    return _runtime_context(target_app).engine


def _get_interaction_manager(target_app: FastAPI | None = None) -> InteractionManager:
    return cast(InteractionManager, _runtime_context(target_app).interaction_manager)


def _get_governed_agent_runtime() -> Any:
    runtime = _runtime_context().governed_agent_runtime
    if runtime is None:
        raise RuntimeError("Governed-agent runtime is unavailable.")
    return runtime


# --- System Endpoints ---


async def health() -> dict[str, str]:
    return {"status": "ok"}


# --- v1 Endpoints ---

v1_router = APIRouter(prefix="/v1", dependencies=[Depends(get_api_key)])


@v1_router.get("/version")
async def get_version() -> dict[str, str]:
    return _filter_operator_payload({"version": __version__, "api": "v1"}, surface="api.version")


async def _observe_runtime_policy() -> RuntimePolicySnapshot:
    # Policy is operator-changeable between requests; capture once before the first await.
    return await _runtime_context().observe_runtime_policy(environment=dict(os.environ), invocation_root=Path.cwd())


def _runtime_policy_process_rules() -> dict[str, Any]:
    runtime_engine = _get_engine()
    if runtime_engine.org and isinstance(getattr(runtime_engine.org, "process_rules", None), dict):
        return dict(runtime_engine.org.process_rules)
    return {}


def _settings_validation_error(errors: list[dict[str, Any]]) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "message": "Invalid settings update",
            "errors": errors,
        },
    )


register_api_domain_routes(
    v1_router, runtime_getter=lambda: _runtime_context(), project_root_getter=lambda: _project_root(),
    runtime_node_getter=lambda: _get_api_runtime_node(), engine_getter=lambda: _get_engine(),
    governed_runtime_getter=lambda: _get_governed_agent_runtime(),
    outbound_filter=lambda payload, surface: _filter_operator_payload(payload, surface=surface),
    observe_policy=lambda: _observe_runtime_policy(), runtime_policy_process_rules=lambda: _runtime_policy_process_rules(),
    load_user_settings=lambda: load_user_settings_async(),
    save_user_settings=lambda settings, **options: save_user_settings_async(settings, **options),
    settings_validation_error=lambda errors: _settings_validation_error(errors),
)


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
