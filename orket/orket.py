# orket/orket.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
import json
import uuid
import asyncio

from orket.llm import LocalModelProvider
from orket.logging import log_event
from orket.state import runtime_state
from orket.agents.agent import Agent
from orket.policy import create_session_policy
from orket.tools import ToolBox, get_tool_map
from orket.schema import EpicConfig, TeamConfig, EnvironmentConfig, RockConfig, IssueConfig
from orket.utils import get_eos_sprint, sanitize_name
from orket.persistence import PersistenceManager
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

async def orchestrate_card(
    card_id: str,
    workspace: Path,
    department: str = "core",
    session_id: str = None,
    build_id: str = None,
    driver_steered: bool = False
) -> Any:
    """
    Orkestrates any specific Card unit (Rock, Epic, or Issue).
    Resolves hierarchy context automatically.
    """
    workspace.mkdir(parents=True, exist_ok=True)
    loader = ConfigLoader(Path("model").resolve(), department)
    db = PersistenceManager()
    
    # 1. Check if card_id refers to an Epic directly
    if card_id in loader.list_assets("epics"):
        return await orchestrate(card_id, workspace, department, session_id, build_id, driver_steered)
    
    # 2. Check if it refers to a Rock
    if card_id in loader.list_assets("rocks"):
        return await orchestrate_rock(card_id, workspace, department, session_id, build_id, driver_steered=driver_steered)

    # 3. Resolve as a standalone Issue by searching all epics
    parent_epic = None
    parent_ename = None
    target_issue = None
    all_epics = loader.list_assets("epics")
    for ename in all_epics:
        try:
            epic = loader.load_asset("epics", ename, EpicConfig)
            for i in epic.issues:
                if i.id == card_id:
                    parent_epic = epic
                    parent_ename = ename
                    target_issue = i
                    break
            if parent_epic: break
        except: continue

    if not parent_epic or not target_issue:
        raise ValueError(f"Card {card_id} not found in {department}.")

    print(f"  [TRACTION] Orkestrating Atomic Card: {card_id} (Parent: {parent_epic.name})")
    
    run_id = session_id or str(uuid.uuid4())[:8]
    active_build = build_id or f"card-build-{card_id}"

    # Ensure in DB
    if not db.get_session(run_id):
        db.start_session(run_id, "issue", card_id, department, f"Direct execution of card {card_id}")
    db.reset_build_issues(active_build) 
    
    return await orchestrate(
        epic_name=parent_ename,
        workspace=workspace,
        department=department,
        session_id=run_id,
        build_id=active_build,
        driver_steered=driver_steered,
        target_issue_id=card_id
    )

async def orchestrate(
    epic_name: str,
    workspace: Path,
    department: str = "core",
    task_override: Optional[str] = None,
    extra_references: List[str] = None,
    session_id: str = None,
    build_id: str = None,
    model_override: str = None,
    interactive_conductor: bool = False,
    driver_steered: bool = False,
    target_issue_id: str = None
) -> Any:
    workspace.mkdir(parents=True, exist_ok=True)
    loader = ConfigLoader(Path("model").resolve(), department)
    epic = loader.load_asset("epics", epic_name, EpicConfig)
    team = loader.load_asset("teams", epic.team, TeamConfig)
    
    # Allow model override
    env = loader.load_asset("environments", epic.environment, EnvironmentConfig)
    if model_override:
        env.model = model_override
    
    final_task = task_override or epic.example_task or "No objective."
    all_refs = epic.references + (extra_references or [])
    
    # Unique Session for Audit, Stable Build for Reuse
    run_id = session_id or str(uuid.uuid4())[:8]
    active_build = build_id or f"build-{sanitize_name(epic_name)}"

    # --- POPULATE BACKLOG ---
    db = PersistenceManager()
    current_sprint = get_eos_sprint()
    
    # Register session in DB if it's new
    if not db.get_session(run_id):
        db.start_session(run_id, "epic", epic.name, department, final_task)
    
    # Check for existing issues in this build
    existing = db.get_build_issues(active_build)
    if len(existing) > 0:
        print(f"  [REUSE] Build '{active_build}' found. Flipping {len(existing)} tasks back to READY.")
        db.reset_build_issues(active_build)
    
    # Ensure epic issues are registered to the build
    for i in epic.issues:
        if not any(ex["id"] == i.id for ex in existing):
            db.add_issue(run_id, i.seat, i.name, i.type, i.priority, current_sprint, i.note, build_id=active_build, issue_id_override=i.id)

    log_event("session_start", {"epic": epic.name, "run_id": run_id, "build_id": active_build}, workspace=workspace)
    
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
        # Get issues specifically for this build
        backlog = db.get_build_issues(active_build)
        ready = [i for i in backlog if i["status"] == "ready"]
        
        # --- STANDALONE CARD FILTER ---
        if target_issue_id:
            ready = [i for i in ready if i["id"] == target_issue_id]

        if not ready: break
            
        issue = ready[0]
        issue_id, seat_name = issue["id"], issue["seat"]
        
        # --- DRIVER STEERING ---
        prompt_patch = None
        if driver_steered:
            print(f"  [STEERING] Consulting Driver for turn {len(transcript)}...")
            from orket.driver import OrketDriver
            driver = OrketDriver()
            
            steering_msg = f"Current state of epic '{epic_name}': {len(transcript)} steps completed. Next planned member is '{seat_name}'. Task: '{issue['summary']}'. Provide a tactical directive or prompt patch for this turn."
            steering_res = await driver.process_request(steering_msg)
            
            log_event("driver_steering", {"insight": steering_res}, workspace, role="DRIVER")
            prompt_patch = f"DRIVER DIRECTIVE: {steering_res}"

        db.update_issue_status(issue_id, "in_progress", assignee=seat_name)
        
        seat = team.seats.get(sanitize_name(seat_name))
        if not seat:
            db.update_issue_status(issue_id, "blocked")
            continue

        desc = f"Seat: {seat_name}.\nISSUE: {issue['summary']}\n"
        desc += "MANDATORY: Use 'write_file' to persist work. One Issue, One Member.\n"
        
        # --- WARM HANDOFF PEAK ---
        next_member = None
        if len(ready) > 1:
            next_member = ready[1]["seat"]

        tools = {}
        for r_name in seat.roles:
            role = team.roles.get(r_name)
            if role:
                desc += f"\nRole {role.name}: {role.description}\n"
                for tn in role.tools:
                    if tn in tool_map: tools[tn] = tool_map[tn]

        print(f"  [ORKESTRATE] {seat_name} -> {issue_id}")
        
        # --- MULTI-TURN TRACTION ---
        turn_count = 0
        max_turns = 5
        
        while turn_count < max_turns:
            agent = Agent(seat_name, desc, tools, provider, next_member=next_member, prompt_patch=prompt_patch)
            
            response = await agent.run(
                task={"description": f"{final_task}\n\nTask: {issue['summary']}"},
                context={"session_id": run_id, "issue_id": issue_id, "workspace": str(workspace), "role": seat_name, "step_index": len(transcript), "turn": turn_count},
                workspace=workspace,
                transcript=transcript
            )
            
            # --- RECORD CREDITS ---
            usage = getattr(response, "usage", {})
            total_tokens = usage.get("total_tokens") or 0
            if total_tokens > 0:
                credits_to_add = (total_tokens / 1000.0) * 0.01
                db.add_credits(issue_id, credits_to_add)
                log_event("credit_charge", {"issue": issue_id, "tokens": total_tokens, "credits": credits_to_add}, workspace, role="SYS")

            res_note = getattr(response, "note", "")
            
            # Add to transcript
            transcript.append({
                "step_index": f"{len(transcript)}.{turn_count}" if turn_count > 0 else len(transcript),
                "role": seat_name, 
                "issue": issue_id, 
                "summary": response.content,
                "note": res_note
            })

            # Check current status in DB
            current_issue = db.get_issue(issue_id)
            
            # If the model called tools, and the task wasn't explicitly finished, we loop.
            if "tools=" in res_note and current_issue and current_issue["status"] == "in_progress":
                print(f"  [TRACTION] {seat_name} executed tools. Continuing turn {turn_count + 1}...")
                turn_count += 1
                desc += f"\n\nCONTINUATION: You just executed tools. Above is the result history. Continue your task until completion."
                continue
            else:
                if current_issue and current_issue["status"] == "in_progress":
                    db.update_issue_status(issue_id, "done")
                break

        # --- HANDSHAKE ROUND (Q&A) ---
        if epic.handshake_enabled and next_member and next_member != seat_name:
            print(f"  [HANDSHAKE] {next_member} reviewing work from {seat_name}...")
            next_agent = Agent(next_member, f"Handoff Reviewer from {seat_name}", {}, provider)
            
            interrogation_task = {
                "description": f"You are receiving a handoff from {seat_name}. Review their final response and memo. Do you have any clarifying questions before you begin your task? If yes, list them clearly. If no, respond exactly with 'READY'."
            }
            
            questions = await next_agent.run(
                task=interrogation_task,
                context={"session_id": run_id, "role": next_member, "handoff_from": seat_name},
                workspace=workspace,
                transcript=transcript
            )
            
            if "READY" not in questions.content.upper():
                log_event("handshake_query", {"from": next_member, "to": seat_name, "questions": questions.content}, workspace, role="SYS")
                print(f"  [HANDSHAKE] {seat_name} answering clarifications for {next_member}...")
                clarification_task = {
                    "description": f"The '{next_member}' has the following questions about your handoff: {questions.content}\n\nPlease provide a concise clarification to ensure they can proceed."
                }
                
                answers = await agent.run(
                    task=clarification_task,
                    context={"session_id": run_id, "role": seat_name, "handoff_to": next_member},
                    workspace=workspace,
                    transcript=transcript
                )
                
                log_event("handshake_clarified", {"from": seat_name, "to": next_member, "answers": answers.content}, workspace, role="SYS")
                
                transcript.append({
                    "step_index": f"{len(transcript)-1}.1",
                    "role": "HANDSHAKE",
                    "summary": f"Q: {questions.content}\nA: {answers.content}"
                })

    log_event("session_end", {"run_id": run_id}, workspace=workspace)
    
    # --- SESSION REPLAYABILITY SNAPSHOT ---
    try:
        snapshot_config = {
            "epic": epic.model_dump(),
            "team": team.model_dump(),
            "env": env.model_dump(),
            "build_id": active_build
        }
        db.record_snapshot(run_id, snapshot_config, transcript)
    except Exception as e:
        print(f"  [WARN] Failed to capture session snapshot: {e}")

    return transcript

async def orchestrate_rock(
    rock_name: str, 
    workspace: Path, 
    department: str = "core", 
    session_id: str = None,
    build_id: str = None,
    task_override: Optional[str] = None,
    driver_steered: bool = False
) -> Dict[str, Any]:
    loader = ConfigLoader(Path("model").resolve(), department)
    rock = loader.load_asset("rocks", rock_name, RockConfig)
    
    sid = session_id or str(uuid.uuid4())[:8]
    active_build = build_id or f"rock-build-{sanitize_name(rock_name)}"
    log_event("rock_start", {"rock": rock.name, "session_id": sid, "build_id": active_build}, workspace=workspace)
    
    final_task = task_override or rock.task or "No objective."
    
    results, prev_ws = [], []
    for entry in rock.epics:
        epic_ws = workspace / entry["epic"]
        res = await orchestrate(
            entry["epic"], 
            epic_ws, 
            entry["department"], 
            final_task, 
            rock.references + prev_ws, 
            session_id=sid,
            build_id=active_build,
            driver_steered=driver_steered
        )
        prev_ws.append(str(epic_ws))
        results.append({"epic": entry["epic"], "transcript": res})

    log_event("rock_end", {"rock": rock.name}, workspace=workspace)
    return {"rock": rock.name, "results": results}