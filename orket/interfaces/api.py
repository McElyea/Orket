import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta, UTC
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Request, APIRouter, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
import os

from orket import __version__
from orket.orchestration.engine import OrchestrationEngine
from orket.infrastructure.async_file_tools import AsyncFileTools
from orket.logging import subscribe_to_events
from orket.state import runtime_state
from orket.hardware import get_metrics_snapshot
from orket.settings import load_user_settings
from orket.decision_nodes.registry import DecisionNodeRegistry


from pydantic import BaseModel, Field

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
    if expected_key and api_key_header != expected_key:
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

origins_str = os.getenv("ORKET_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
api_runtime_node = DecisionNodeRegistry().resolve_api_runtime()
origins = api_runtime_node.parse_allowed_origins(origins_str)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
engine = OrchestrationEngine(PROJECT_ROOT / "workspace" / "default")

# --- System Endpoints ---

@app.get("/health")
async def health(): return {"status": "ok", "organization": "Orket"}

# --- v1 Endpoints ---

@v1_router.get("/version")
async def get_version():
    return {"version": __version__, "api": "v1"}

@v1_router.post("/system/clear-logs")
async def clear_logs():
    log_path = "workspace/default/orket.log"
    fs = AsyncFileTools(PROJECT_ROOT)
    try:
        await fs.write_file(log_path, "")
    except (PermissionError, FileNotFoundError, OSError):
        pass
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
    fs = AsyncFileTools(PROJECT_ROOT)
    try:
        content = await fs.read_file(path)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    return {"content": content}

@v1_router.post("/system/save")
async def save_system_file(req: SaveFileRequest):
    fs = AsyncFileTools(PROJECT_ROOT)
    try:
        await fs.write_file(req.path, req.content)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"ok": True}

@v1_router.get("/system/calendar")
async def get_calendar():
    from orket.utils import get_eos_sprint
    now = datetime.now(UTC)
    return {
        "current_sprint": get_eos_sprint(now),
        "sprint_start": (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d"),
        "sprint_end": (now + timedelta(days=4-now.weekday())).strftime("%Y-%m-%d")
    }

@v1_router.post("/system/run-active")
async def run_active_asset(req: RunAssetRequest):
    session_id = api_runtime_node.create_session_id()

    asset_id = api_runtime_node.resolve_asset_id(req.path, req.issue_id)
    if not asset_id: raise HTTPException(status_code=400, detail="No asset ID provided.")

    print(f"  [API] v1 EXECUTE: {asset_id} (Type: {req.type}, Session: {session_id})")
    task = asyncio.create_task(engine.run_card(asset_id, build_id=req.build_id, session_id=session_id))
    await runtime_state.add_task(session_id, task)
    return {"session_id": session_id}

@v1_router.get("/runs")
async def list_runs(): return await engine.sessions.get_recent_runs()

@v1_router.get("/runs/{session_id}/metrics")
async def get_run_metrics(session_id: str):
    from orket.logging import get_member_metrics
    workspace = api_runtime_node.resolve_member_metrics_workspace(PROJECT_ROOT, session_id)
    return get_member_metrics(workspace)

@v1_router.get("/runs/{session_id}/backlog")
async def get_backlog(session_id: str): return await engine.sessions.get_session_issues(session_id)

@v1_router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str):
    session = await engine.sessions.get_session(session_id)
    if not session: raise HTTPException(404)
    return session

@v1_router.get("/sessions/{session_id}/snapshot")
async def get_session_snapshot(session_id: str):
    snapshot = await engine.snapshots.get(session_id)
    if not snapshot: raise HTTPException(404)
    return snapshot

@v1_router.get("/sandboxes")
async def list_sandboxes():
    return await engine.get_sandboxes()

@v1_router.post("/sandboxes/{sandbox_id}/stop")
async def stop_sandbox(sandbox_id: str):
    await engine.stop_sandbox(sandbox_id)
    return {"ok": True}

@v1_router.get("/sandboxes/{sandbox_id}/logs")
async def get_sandbox_logs(sandbox_id: str, service: Optional[str] = None):
    from orket.orket import ExecutionPipeline
    pipeline = ExecutionPipeline(PROJECT_ROOT / "workspace" / "default")
    return {"logs": pipeline.sandbox_orchestrator.get_logs(sandbox_id, service)}

@v1_router.get("/system/board")
async def get_system_board(dept: str = "core"):
    return engine.get_board()

@v1_router.get("/system/preview-asset")
async def preview_asset(path: str, issue_id: Optional[str] = None):
    from orket.preview import PreviewBuilder
    target = api_runtime_node.resolve_preview_target(path, issue_id)
    builder = PreviewBuilder(PROJECT_ROOT / "model")
    if target["mode"] == "issue":
        res = await builder.build_issue_preview(issue_id, target["asset_name"], target["department"])
    elif target["mode"] == "rock":
        res = await builder.build_rock_preview(target["asset_name"], target["department"])
    else:
        res = await builder.build_epic_preview(target["asset_name"], target["department"])
    return res

@v1_router.post("/system/chat-driver")
async def chat_driver(req: ChatDriverRequest):
    from orket.driver import OrketDriver
    driver = OrketDriver()
    response = await driver.process_request(req.message)
    return {"response": response}

app.include_router(v1_router)

# --- WS ---

async def event_broadcaster():
    while True:
        record = await runtime_state.event_queue.get()
        for ws in await runtime_state.get_websockets():
            try: await ws.send_json(record)
            except (WebSocketDisconnect, RuntimeError, ValueError):
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
