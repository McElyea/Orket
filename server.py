# server.py
import asyncio
from typing import List, Optional, Dict, Any
from pathlib import Path
import uuid
import json
from datetime import datetime, timedelta

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware

from orket.orket import orchestrate, orchestrate_rock
from orket.logging import subscribe_to_events
from orket.state import runtime_state
from orket.hardware import get_current_profile, get_metrics_snapshot
from orket.settings import load_user_settings
from orket.persistence import PersistenceManager

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------
db = PersistenceManager()
settings = load_user_settings()
PROJECT_ROOT = Path(__file__).parent.resolve()

app = FastAPI(title="Orket EOS Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health(): return {"status": "ok", "port": 8082}

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
        is_launchable, asset_type = False, None
        if not is_dir and p.suffix == ".json":
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                if "epics" in raw: is_launchable, asset_type = True, "rock"
                elif "tracs" in raw or "stories" in raw: is_launchable, asset_type = True, "epic"
            except: pass
        items.append({"name": p.name, "is_dir": is_dir, "ext": p.suffix, "is_launchable": is_launchable, "asset_type": asset_type})
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return {"items": items, "path": path}

@app.get("/system/read")
async def read_system_file(path: str):
    target = (PROJECT_ROOT / path).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)): raise HTTPException(403)
    return {"content": target.read_text(encoding="utf-8")}

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
async def run_active_asset(data: Dict[str, str] = Body(...)):
    path_str = data.get("path")
    if not path_str: raise HTTPException(400)
    p = Path(path_str)
    asset_name = p.stem
    
    dept = "core"
    if "model" in p.parts:
        idx = p.parts.index("model")
        if len(p.parts) > idx + 1: dept = p.parts[idx+1]

    session_id = str(uuid.uuid4())[:8]
    print(f"  [LAUNCH] {asset_name} (ID: {session_id})")

    # Rocks and Epics are high-level Cards. Issues are operational Cards.
    if "rocks" in str(p):
        db.start_session(session_id, "rock", asset_name, dept, "Ignited")
        task = asyncio.create_task(run_rock_task(session_id, asset_name, dept))
        runtime_state.active_tasks[session_id] = task
        return {"session_id": session_id, "type": "rock"}
    else:
        db.start_session(session_id, "epic", asset_name, dept, "Ignited")
        task = asyncio.create_task(run_epic_task(session_id, asset_name, dept))
        runtime_state.active_tasks[session_id] = task
        return {"session_id": session_id, "type": "epic"}

@app.post("/system/halt")
async def halt_session(data: Dict[str, str] = Body(...)):
    session_id = data.get("session_id")
    if not session_id:
        # Halt ALL active tasks if no session_id provided
        count = 0
        for sid, task in list(runtime_state.active_tasks.items()):
            task.cancel()
            count += 1
        return {"ok": True, "message": f"Halted {count} active sessions."}
    
    if session_id in runtime_state.active_tasks:
        runtime_state.active_tasks[session_id].cancel()
        return {"ok": True, "message": f"Session {session_id} halted."}
    return {"ok": False, "error": "Session not found or not active."}

@app.post("/system/refresh-engines")
async def refresh_engines():
    from orket.discovery import refresh_engine_mappings
    recs = refresh_engine_mappings()
    return {"ok": True, "recommendations": recs}

@app.get("/system/recommendations")
async def get_system_recommendations():
    from orket.discovery import get_engine_recommendations
    return {"suggestions": get_engine_recommendations()}

@app.get("/system/board")
async def get_system_board(dept: str = "core"):
    from orket.board import get_board_hierarchy
    return get_board_hierarchy(dept)

@app.post("/system/chat-driver")
async def chat_driver(data: Dict[str, str] = Body(...)):
    from orket.driver import OrketDriver
    message = data.get("message")
    if not message: raise HTTPException(400)
    
    driver = OrketDriver()
    response = await driver.process_request(message)
    return {"response": response}

@app.get("/runs")
async def list_runs(): return db.get_recent_runs()

@app.get("/runs/{session_id}/metrics")
async def get_run_metrics(session_id: str):
    from orket.logging import get_member_metrics
    workspace = Path(f"workspace/runs/{session_id}")
    if not workspace.exists():
        # Fallback to default workspace if not a specific run
        workspace = Path("workspace/default")
    return get_member_metrics(workspace)

@app.get("/runs/{session_id}/backlog")
async def get_backlog(session_id: str): return db.get_session_issues(session_id)

@app.patch("/backlog/{issue_id}")
async def patch_issue(issue_id: str, data: Dict[str, Any] = Body(...)):
    if "status" in data:
        db.update_issue_status(issue_id, data["status"])
    if "resolution" in data:
        db.update_issue_resolution(issue_id, data["resolution"])
    if "credits" in data:
        db.add_credits(issue_id, data["credits"])
    return {"ok": True}

@app.get("/backlog/{issue_id}/comments")
async def get_comments(issue_id: str):
    return db.get_comments(issue_id)

@app.post("/backlog/{issue_id}/comments")
async def post_comment(issue_id: str, data: Dict[str, str] = Body(...)):
    db.add_comment(issue_id, data.get("author", "User"), data["content"])
    return {"ok": True}

@app.post("/conductor/intervene")
async def conductor_intervene(session_id: str = Body(...), seat: str = Body(...), action: str = Body(...)):
    if session_id not in runtime_state.interventions: runtime_state.interventions[session_id] = {}
    runtime_state.interventions[session_id][seat] = action
    return {"ok": True}

# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

async def run_epic_task(session_id: str, epic_name: str, department: str):
    workspace = Path(f"workspace/runs/{session_id}")
    try:
        transcript = await orchestrate(epic_name, workspace, department, session_id=session_id)
        db.update_session_status(session_id, "completed", 0, transcript)
    except asyncio.CancelledError:
        print(f"  [HALT] {session_id} canceled by user.")
        db.update_session_status(session_id, "halted")
    except Exception as e:
        print(f"  [FAIL] {session_id}: {e}")
        db.update_session_status(session_id, "failed")
    finally:
        runtime_state.active_tasks.pop(session_id, None)

async def run_rock_task(session_id: str, rock_name: str, department: str):
    workspace = Path(f"workspace/runs/{session_id}")
    try:
        from orket.orket import orchestrate_rock
        result = await orchestrate_rock(rock_name, workspace, department, session_id=session_id)
        db.update_session_status(session_id, "completed", 0, result)
    except asyncio.CancelledError:
        print(f"  [HALT] {session_id} canceled by user.")
        db.update_session_status(session_id, "halted")
    except Exception as e:
        print(f"  [FAIL] {session_id}: {e}")
        db.update_session_status(session_id, "failed")
    finally:
        runtime_state.active_tasks.pop(session_id, None)

# ---------------------------------------------------------------------------
# WS
# ---------------------------------------------------------------------------

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8082, reload=True)