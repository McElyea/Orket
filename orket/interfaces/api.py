import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, APIRouter, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
import os

from orket import __version__
from orket.logging import subscribe_to_events, log_event
from orket.state import runtime_state
from orket.hardware import get_metrics_snapshot
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.time_utils import now_local


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

@v1_router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str):
    log_event("api_session_detail", {"session_id": session_id}, PROJECT_ROOT)
    invocation = api_runtime_node.resolve_session_detail_invocation(session_id)
    session = await _invoke_async_method(engine.sessions, invocation, "session")
    if not session:
        raise HTTPException(**api_runtime_node.session_detail_not_found_error(session_id))
    return session

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
    selectors = [bool(req.card_ids), bool(req.build_id), bool(req.related_tokens)]
    if not any(selectors):
        raise HTTPException(status_code=400, detail="Provide at least one selector: card_ids, build_id, or related_tokens")

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

    # Keep deterministic output for clients.
    archived_ids = sorted(set(archived_ids))
    missing_ids = sorted(set(missing_ids))
    archived_count += len(archived_ids)

    return {
        "ok": True,
        "archived_count": archived_count,
        "archived_ids": archived_ids,
        "missing_ids": missing_ids,
    }

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
    await websocket.accept()
    await runtime_state.add_websocket(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        await runtime_state.remove_websocket(websocket)
