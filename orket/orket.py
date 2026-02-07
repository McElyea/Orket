# orket/orket.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
import json
import uuid

from orket.llm import LocalModelProvider
from orket.logging import log_event
from orket.state import runtime_state
from orket.agents.agent import Agent
from orket.policy import create_session_policy
from orket.tools import ToolBox, get_tool_map
from orket.schema import EpicConfig, TeamConfig, EnvironmentConfig, RockConfig
from orket.utils import get_eos_sprint, sanitize_name
from pydantic import BaseModel

class ConfigLoader:
    def __init__(self, model_root: Path, department: str = "core"):
        self.dept_path = model_root / department

    def load_asset(self, category: str, name: str, model_type: Type[BaseModel]) -> Any:
        path = self.dept_path / category / f"{name}.json"
        if not path.exists():
            core_path = self.dept_path.parent / "core" / category / f"{name}.json"
            if core_path.exists(): path = core_path
            else: raise FileNotFoundError(f"Asset '{name}' not found")
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))

    def list_assets(self, category: str) -> List[str]:
        assets = set()
        paths = [self.dept_path / category, self.dept_path.parent / "core" / category]
        for p in paths:
            if p.exists():
                for f in p.glob("*.json"):
                    assets.add(f.stem)
        return sorted(list(assets))

async def orchestrate(
    epic_name: str,
    workspace: Path,
    department: str = "core",
    task_override: Optional[str] = None,
    extra_references: List[str] = None,
    session_id: str = None
) -> Any:
    workspace.mkdir(parents=True, exist_ok=True)
    loader = ConfigLoader(Path("model").resolve(), department)
    epic = loader.load_asset("epics", epic_name, EpicConfig)
    team = loader.load_asset("teams", epic.team, TeamConfig)
    env = loader.load_asset("environments", epic.environment, EnvironmentConfig)
    
    final_task = task_override or epic.example_task or "No objective."
    all_refs = epic.references + (extra_references or [])
    run_id = session_id or str(uuid.uuid4())[:8]

    # --- POPULATE BACKLOG ---
    from orket.persistence import PersistenceManager
    db = PersistenceManager()
    current_sprint = get_eos_sprint()
    
    # Only populate if this is a fresh Epic run (not inherited from Rock)
    existing = db.get_session_books(run_id)
    for b in epic.books:
        # Check if this specific book summary already exists to avoid dupes in Rock runs
        if not any(ex["summary"] == b.summary for ex in existing):
            db.add_book(run_id, b.seat, b.summary, b.type, b.priority, current_sprint, b.note)

    log_event("session_start", {"epic": epic.name, "run_id": run_id}, workspace=workspace)
    
    policy = create_session_policy(str(workspace), all_refs)
    toolbox = ToolBox(policy, str(workspace), all_refs)
    tool_map = get_tool_map(toolbox)
    provider = LocalModelProvider(
        model=env.model, 
        temperature=env.temperature, 
        seed=env.seed,
        timeout=env.timeout
    )

    transcript = []

    # --- TRACTION LOOP ---
    while True:
        backlog = db.get_session_books(run_id)
        # Filter for Books belonging to THIS Epic context or added by it
        ready = [b for b in backlog if b["status"] == "ready"]
        
        if not ready: break
            
        book = ready[0]
        book_id, seat_name = book["id"], book["seat"]

        # CONDUCTOR PULL
        if run_id in runtime_state.interventions and seat_name in runtime_state.interventions[run_id]:
            if runtime_state.interventions[run_id][seat_name] == "pull":
                db.update_book_status(book_id, "ready", assignee=None)
                continue

        db.update_book_status(book_id, "in_progress", assignee=seat_name)
        
        seat = team.seats.get(sanitize_name(seat_name))
        if not seat:
            db.update_book_status(book_id, "blocked")
            continue

        desc = f"Seat: {seat_name}.\nBOOK: {book['summary']}\n"
        desc += "MANDATORY: Use 'write_file' to persist work. One Book, One Member.\n"
        
        tools = {}
        for r_name in seat.roles:
            role = team.roles.get(r_name)
            if role:
                desc += f"\nRole {role.name}: {role.description}\n"
                for tn in role.tools:
                    if tn in tool_map: tools[tn] = tool_map[tn]

        print(f"  [TRACTION] {seat_name} -> {book_id}")
        agent = Agent(seat_name, desc, tools, provider)
        response = await agent.run(
            task={"description": f"{final_task}\n\nTask: {book['summary']}"},
            context={"session_id": run_id, "book_id": book_id, "workspace": str(workspace), "role": seat_name},
            workspace=workspace,
            transcript=transcript
        )
        
        db.update_book_status(book_id, "done")
        transcript.append({"role": seat_name, "book": book_id, "summary": response.content})

    log_event("session_end", {"run_id": run_id}, workspace=workspace)
    return transcript

async def orchestrate_rock(rock_name: str, workspace: Path, department: str = "core", session_id: str = None) -> Dict[str, Any]:
    loader = ConfigLoader(Path("model").resolve(), department)
    rock = loader.load_asset("rocks", rock_name, RockConfig)
    
    sid = session_id or str(uuid.uuid4())[:8]
    log_event("rock_start", {"rock": rock.name, "session_id": sid}, workspace=workspace)
    
    results, prev_ws = [], []
    for entry in rock.epics:
        epic_ws = workspace / entry["epic"]
        res = await orchestrate(entry["epic"], epic_ws, entry["department"], rock.task, rock.references + prev_ws, session_id=sid)
        prev_ws.append(str(epic_ws))
        results.append({"epic": entry["epic"], "transcript": res})

    log_event("rock_end", {"rock": rock.name}, workspace=workspace)
    return {"rock": rock.name, "results": results}
