import asyncio
from pathlib import Path
from datetime import datetime, UTC
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


from pydantic import BaseModel

api_runtime_node = DecisionNodeRegistry().resolve_api_runtime()


def _resolve_async_method(target: object, invocation: dict, error_prefix: str):
    method_name = invocation["method_name"]
    method = getattr(target, method_name, None)
    if method is None:
        raise HTTPException(status_code=400, detail=f"Unsupported {error_prefix} method '{method_name}'.")
    return method


def _resolve_sync_method(target: object, method_name: str, error_prefix: str):
    method = getattr(target, method_name, None)
    if method is None:
        raise HTTPException(status_code=400, detail=f"Unsupported {error_prefix} method '{method_name}'.")
    return method


async def _invoke_async_method(target: object, invocation: dict, error_prefix: str):
    method = _resolve_async_method(target, invocation, error_prefix)
    return await method(*invocation.get("args", []), **invocation.get("kwargs", {}))

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

# Security dependency
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    expected_key = os.getenv("ORKET_API_KEY")
    if not api_runtime_node.is_api_key_valid(expected_key, api_key_header):
        raise HTTPException(
            status_code=403,
            detail="Could not validate credentials",
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
        await fs.write_file(log_path, "")
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
        "timestamp": datetime.now(UTC).isoformat(),
        "active_tasks": len(runtime_state.active_tasks)  # Read-only len() is safe without lock
    }

@v1_router.get("/system/metrics")
async def get_metrics():
    return api_runtime_node.normalize_metrics(get_metrics_snapshot())

@v1_router.get("/system/explorer")
async def list_system_files(path: str = "."):
    target = api_runtime_node.resolve_explorer_path(PROJECT_ROOT, path)
    if target is None:
        raise HTTPException(403)
    if not target.exists():
        return {"items": [], "path": path}
    
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
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    return {"content": content}

@v1_router.post("/system/save")
async def save_system_file(req: SaveFileRequest):
    fs = api_runtime_node.create_file_tools(PROJECT_ROOT)
    try:
        invocation = api_runtime_node.resolve_save_invocation(req.path, req.content)
        await _invoke_async_method(fs, invocation, "save")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"ok": True}

@v1_router.get("/system/calendar")
async def get_calendar():
    from orket.utils import get_eos_sprint
    now = datetime.now(UTC)
    calendar_window = api_runtime_node.calendar_window(now)
    return {
        "current_sprint": get_eos_sprint(now),
        "sprint_start": calendar_window["sprint_start"],
        "sprint_end": calendar_window["sprint_end"],
    }

@v1_router.post("/system/run-active")
async def run_active_asset(req: RunAssetRequest):
    session_id = api_runtime_node.create_session_id()

    asset_id = api_runtime_node.resolve_asset_id(req.path, req.issue_id)
    if not asset_id: raise HTTPException(status_code=400, detail="No asset ID provided.")

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
    method = _resolve_async_method(engine, invocation, "run")
    task = asyncio.create_task(method(*invocation.get("args", []), **invocation.get("kwargs", {})))
    await runtime_state.add_task(session_id, task)
    return {"session_id": session_id}

@v1_router.get("/runs")
async def list_runs():
    invocation = api_runtime_node.resolve_runs_invocation()
    return await _invoke_async_method(engine.sessions, invocation, "runs")

@v1_router.get("/runs/{session_id}/metrics")
async def get_run_metrics(session_id: str):
    from orket.logging import get_member_metrics
    log_event("api_run_metrics", {"session_id": session_id}, PROJECT_ROOT)
    workspace = api_runtime_node.resolve_member_metrics_workspace(PROJECT_ROOT, session_id)
    return get_member_metrics(workspace)

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
    if not session: raise HTTPException(404)
    return session

@v1_router.get("/sessions/{session_id}/snapshot")
async def get_session_snapshot(session_id: str):
    log_event("api_session_snapshot", {"session_id": session_id}, PROJECT_ROOT)
    invocation = api_runtime_node.resolve_session_snapshot_invocation(session_id)
    snapshot = await _invoke_async_method(engine.snapshots, invocation, "snapshot")
    if not snapshot: raise HTTPException(404)
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
    get_logs = _resolve_sync_method(pipeline.sandbox_orchestrator, "get_logs", "sandbox logs")
    return {"logs": get_logs(sandbox_id, service)}

@v1_router.get("/system/board")
async def get_system_board(dept: str = "core"):
    return api_runtime_node.resolve_system_board(dept)

@v1_router.get("/system/preview-asset")
async def preview_asset(path: str, issue_id: Optional[str] = None):
    target = api_runtime_node.resolve_preview_target(path, issue_id)
    invocation = api_runtime_node.resolve_preview_invocation(target, issue_id)
    builder = api_runtime_node.create_preview_builder(PROJECT_ROOT / "model")
    build_method = getattr(builder, invocation["method_name"], None)
    if build_method is None:
        raise HTTPException(status_code=400, detail=f"Unsupported preview mode '{target['mode']}'.")
    return await build_method(*invocation["args"])

@v1_router.post("/system/chat-driver")
async def chat_driver(req: ChatDriverRequest):
    driver = api_runtime_node.create_chat_driver()
    response = await driver.process_request(req.message)
    return {"response": response}

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
