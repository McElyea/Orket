import asyncio
import uuid
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware

from orket.orchestration.engine import OrchestrationEngine
from orket.logging import subscribe_to_events
from orket.state import runtime_state
from orket.hardware import get_metrics_snapshot
from orket.settings import load_user_settings

app = FastAPI(title="McElyea Orket EOS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
engine = OrchestrationEngine(PROJECT_ROOT / "workspace" / "default")

# --- System Endpoints ---

@app.get("/health")
async def health(): return {"status": "ok", "organization": "McElyea"}

@app.get("/system/metrics")
async def get_metrics(): return get_metrics_snapshot()

@app.get("/system/explorer")
async def list_system_files(path: str = "."):
    rel_path = path.strip("./") if path and path != "." else ""
    target = (PROJECT_ROOT / rel_path).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)): raise HTTPException(403)
    if not target.exists(): return {"items": [], "path": path}
    
    items = []
    for p in target.iterdir():
        if p.name.startswith(".") or "__pycache__" in p.name or p.name == "node_modules": continue
        is_dir = p.is_dir()
        items.append({"name": p.name, "is_dir": is_dir, "ext": p.suffix})
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return {"items": items, "path": path}

@app.get("/system/read")
async def read_system_file(path: str):
    target = (PROJECT_ROOT / path).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)): raise HTTPException(403)
    return {"content": target.read_text(encoding="utf-8")}

@app.post("/system/save")
async def save_system_file(data: Dict[str, str] = Body(...)):
    path_str = data.get("path")
    content = data.get("content")
    if not path_str or content is None: raise HTTPException(400)
    target = (PROJECT_ROOT / path_str).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)): raise HTTPException(403)
    target.write_text(content, encoding="utf-8")
    return {"ok": True}

@app.get("/system/calendar")
async def get_calendar():
    from orket.utils import get_eos_sprint
    now = datetime.now()
    return {
        "current_sprint": get_eos_sprint(now),
        "sprint_start": (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d"),
        "sprint_end": (now + timedelta(days=4-now.weekday())).strftime("%Y-%m-%d")
    }

@app.post("/system/run-active")
async def run_active_asset(data: Dict[str, Any] = Body(...)):
    path_str = data.get("path")
    build_id = data.get("build_id")
    asset_type = data.get("type")
    issue_id = data.get("issue_id")
    session_id = str(uuid.uuid4())[:8]

    # If it's a specific issue, run that ID. Otherwise, use the filename stem.
    asset_id = issue_id if issue_id else Path(path_str).stem if path_str else None
    
    if not asset_id:
        raise HTTPException(status_code=400, detail="No asset ID provided.")

    print(f"  [API] EXECUTE: {asset_id} (Type: {asset_type}, Session: {session_id})")

    task = asyncio.create_task(engine.run_card(asset_id, build_id=build_id, session_id=session_id))
    runtime_state.active_tasks[session_id] = task
    return {"session_id": session_id}

@app.get("/runs")
async def list_runs(): return engine.sessions.get_recent_runs()

@app.get("/runs/{session_id}/metrics")
async def get_run_metrics(session_id: str):
    from orket.logging import get_member_metrics
    workspace = PROJECT_ROOT / "workspace" / "runs" / session_id
    if not workspace.exists(): workspace = PROJECT_ROOT / "workspace" / "default"
    return get_member_metrics(workspace)

@app.get("/runs/{session_id}/backlog")
async def get_backlog(session_id: str): return engine.sessions.get_session_issues(session_id)

@app.get("/system/board")
async def get_system_board(dept: str = "core"):
    return engine.get_board()

@app.get("/system/preview-asset")
async def preview_asset(path: str, issue_id: Optional[str] = None):
    from orket.preview import PreviewBuilder
    p = Path(path)
    asset_name = p.stem
    
    dept = "core"
    if "model" in p.parts:
        idx = p.parts.index("model")
        if len(p.parts) > idx + 1: dept = p.parts[idx+1]
        
    builder = PreviewBuilder(PROJECT_ROOT / "model")
    if issue_id:
        res = await builder.build_issue_preview(issue_id, asset_name, dept)
    elif "rocks" in str(p):
        res = await builder.build_rock_preview(asset_name, dept)
    else:
        res = await builder.build_epic_preview(asset_name, dept)
        
    return res

@app.post("/system/chat-driver")
async def chat_driver(data: Dict[str, str] = Body(...)):
    from orket.driver import OrketDriver
    message = data.get("message")
    if not message: raise HTTPException(400)
    driver = OrketDriver()
    response = await driver.process_request(message)
    return {"response": response}

# --- WS ---

async def event_broadcaster():
    while True:
        record = await runtime_state.event_queue.get()
        for ws in list(runtime_state.active_websockets):
            try: await ws.send_json(record)
            except: 
                if ws in runtime_state.active_websockets: runtime_state.active_websockets.remove(ws)
        runtime_state.event_queue.task_done()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(event_broadcaster())
    def on_log_record(record):
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(runtime_state.event_queue.put_nowait, record)
    subscribe_to_events(on_log_record)

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    runtime_state.active_websockets.append(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in runtime_state.active_websockets: runtime_state.active_websockets.remove(websocket)