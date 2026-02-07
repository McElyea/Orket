# server.py
import asyncio
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
import uuid
import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orket.orket import orchestrate, orchestrate_rock, ConfigLoader
from orket.logging import subscribe_to_events, unsubscribe_from_events
from orket.schema import EpicConfig, TeamConfig, EnvironmentConfig, RockConfig, RoleConfig, SeatConfig
from orket.hardware import get_current_profile

app = FastAPI(title="Orket EOS Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class SessionState:
    def __init__(self):
        self.active_websockets: List[WebSocket] = []
        self.runs: Dict[str, Any] = {}
        self.event_queue = asyncio.Queue()

state = SessionState()

# ---------------------------------------------------------------------------
# Background Tasks
# ---------------------------------------------------------------------------
async def event_broadcaster():
    while True:
        record = await state.event_queue.get()
        dead_sockets = []
        for ws in state.active_websockets:
            try:
                await ws.send_json(record)
            except:
                dead_sockets.append(ws)
        for ws in dead_sockets:
            if ws in state.active_websockets:
                state.active_websockets.remove(ws)
        state.event_queue.task_done()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(event_broadcaster())
    def on_log_record(record):
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(state.event_queue.put_nowait, record)
    subscribe_to_events(on_log_record)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class EpicRequest(BaseModel):
    epic: str
    department: str = "core"
    task_override: Optional[str] = None
    model_override: Optional[str] = None

class RockRequest(BaseModel):
    rock: str
    department: str = "core"
    task_override: Optional[str] = None

# ---------------------------------------------------------------------------
# System & Discovery Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "framework": "EOS"}

@app.get("/hardware")
async def get_hardware():
    return get_current_profile()

@app.get("/departments")
async def list_departments():
    model_root = Path("model")
    return {"departments": [d.name for d in model_root.iterdir() if d.is_dir()]}

@app.get("/departments/{dept}/assets")
async def get_dept_assets(dept: str):
    loader = ConfigLoader(Path("model"), dept)
    return {
        "rocks": loader.list_assets("rocks"),
        "epics": loader.list_assets("epics"),
        "teams": loader.list_assets("teams"),
        "environments": loader.list_assets("environments")
    }

# ---------------------------------------------------------------------------
# Asset CRUD (UI Editor Support)
# ---------------------------------------------------------------------------

@app.get("/departments/{dept}/{category}/{name}")
async def get_asset(dept: str, category: str, name: str):
    loader = ConfigLoader(Path("model"), dept)
    # Map category to schema model
    schema_map = {
        "epics": EpicConfig,
        "teams": TeamConfig,
        "rocks": RockConfig,
        "environments": EnvironmentConfig
    }
    if category not in schema_map: raise HTTPException(400, "Invalid category")
    try:
        return loader.load_asset(category, name, schema_map[category])
    except Exception as e: raise HTTPException(404, str(e))

@app.post("/departments/{dept}/{category}/{name}")
async def save_asset(dept: str, category: str, name: str, data: Dict[str, Any] = Body(...)):
    """Saves or updates an EOS asset JSON file."""
    model_root = Path("model")
    dest_dir = model_root / dept / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = dest_dir / f"{name}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return {"ok": True, "path": str(file_path)}

# ---------------------------------------------------------------------------
# Execution & Run Management
# ---------------------------------------------------------------------------

@app.get("/runs")
async def list_runs():
    return state.runs

@app.get("/runs/{session_id}")
async def get_run_status(session_id: str):
    if session_id not in state.runs: raise HTTPException(404, "Run not found")
    return state.runs[session_id]

@app.post("/epics/run")
async def run_epic(req: EpicRequest):
    session_id = str(uuid.uuid4())
    state.runs[session_id] = {"status": "running", "type": "epic", "name": req.epic, "department": req.department}
    asyncio.create_task(run_epic_task(session_id, req))
    return {"session_id": session_id}

@app.post("/rocks/run")
async def run_rock(req: RockRequest):
    session_id = str(uuid.uuid4())
    state.runs[session_id] = {"status": "running", "type": "rock", "name": req.rock, "department": req.department}
    asyncio.create_task(run_rock_task(session_id, req))
    return {"session_id": session_id}

async def run_epic_task(session_id: str, req: EpicRequest):
    workspace = Path(f"workspace/runs/{session_id}")
    try:
        transcript = await orchestrate(req.epic, workspace, req.department, req.model_override, req.task_override)
        state.runs[session_id].update({"status": "completed", "transcript": transcript})
    except Exception as e:
        state.runs[session_id].update({"status": "failed", "error": str(e)})

async def run_rock_task(session_id: str, req: RockRequest):
    workspace = Path(f"workspace/runs/{session_id}")
    try:
        result = await orchestrate_rock(req.rock, workspace, req.department, req.task_override)
        state.runs[session_id].update({"status": "completed", "result": result})
    except Exception as e:
        state.runs[session_id].update({"status": "failed", "error": str(e)})

# ---------------------------------------------------------------------------
# Workspace Explorer
# ---------------------------------------------------------------------------

@app.get("/workspaces/{session_id}/files")
async def list_workspace_files(session_id: str, path: str = "."):
    base = Path(f"workspace/runs/{session_id}")
    target = (base / path).resolve()
    
    # Security: Ensure we don't escape the workspace
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(403, "Access Denied")
    
    if not target.exists(): return {"items": []}
    
    items = []
    for p in target.iterdir():
        items.append({
            "name": p.name,
            "is_dir": p.is_dir(),
            "size": p.stat().st_size if not p.is_dir() else 0,
            "ext": p.suffix
        })
    return {"items": items, "path": path}

# ---------------------------------------------------------------------------
# Real-time Events
# ---------------------------------------------------------------------------

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.active_websockets.append(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in state.active_websockets:
            state.active_websockets.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)