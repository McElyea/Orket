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
from orket.schema import EpicConfig, TeamConfig, EnvironmentConfig, RockConfig, IssueConfig, CardStatus
from orket.utils import get_eos_sprint, sanitize_name
from orket.exceptions import CardNotFound, ExecutionFailed, StateConflict
from orket.infrastructure.sqlite_repositories import SQLiteCardRepository, SQLiteSessionRepository, SQLiteSnapshotRepository
from orket.domain.execution import ExecutionTurn
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# 1. Configuration & Asset Loading (Application Service)
# ---------------------------------------------------------------------------

class ConfigLoader:
    def __init__(self, model_root: Path, department: str = "core"):
        self.dept_path = model_root / department

    def load_asset(self, category: str, name: str, model_type: Type[BaseModel]) -> Any:
        path = self.dept_path / category / f"{name}.json"
        if not path.exists():
            core_path = self.dept_path.parent / "core" / category / f"{name}.json"
            if core_path.exists(): path = core_path
            else: raise CardNotFound(f"Asset '{name}' not found in category '{category}'.")
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))

    def list_assets(self, category: str) -> List[str]:
        assets = set()
        paths = [self.dept_path / category, self.dept_path.parent / "core" / category]
        for p in paths:
            if p.exists():
                for f in p.glob("*.json"):
                    assets.add(f.stem)
        return sorted(list(assets))

# ---------------------------------------------------------------------------
# 2. The Execution Pipeline (Explicit Orchestration Flow)
# ---------------------------------------------------------------------------

from orket.orchestration.notes import NoteStore, Note

class ExecutionPipeline:
    """
    The central engine for Orket Unit execution.
    Load → Validate → Plan → Execute → Persist → Report
    """
    def __init__(self, workspace: Path, department: str = "core"):
        self.workspace = workspace
        self.department = department
        self.loader = ConfigLoader(Path("model").resolve(), department)
        
        # Load Organization
        org_path = Path("model/organization.json")
        if org_path.exists():
            from orket.schema import OrganizationConfig
            self.org = OrganizationConfig.model_validate_json(org_path.read_text(encoding="utf-8"))
        else:
            self.org = None
        
        db_path = "orket_persistence.db"
        self.cards = SQLiteCardRepository(db_path)
        self.sessions = SQLiteSessionRepository(db_path)
        self.snapshots = SQLiteSnapshotRepository(db_path)
        
        self.notes = NoteStore()
        self.transcript = []

    async def run_card(self, card_id: str, **kwargs) -> Any:
        if card_id in self.loader.list_assets("epics"):
            return await self.run_epic(card_id, **kwargs)
        if card_id in self.loader.list_assets("rocks"):
            return await self.run_rock(card_id, **kwargs)

        parent_epic, parent_ename, target_issue = self._find_parent_epic(card_id)
        if not parent_epic: raise CardNotFound(f"Card {card_id} not found.")
        print(f"  [PIPELINE] Executing Atomic Issue: {card_id} (Parent: {parent_epic.name})")
        return await self.run_epic(parent_ename, target_issue_id=card_id, **kwargs)

    async def run_epic(self, epic_name: str, build_id: str = None, session_id: str = None, driver_steered: bool = False, target_issue_id: str = None, **kwargs) -> List[Dict]:
        epic = self.loader.load_asset("epics", epic_name, EpicConfig)
        team = self.loader.load_asset("teams", epic.team, TeamConfig)
        env = self.loader.load_asset("environments", epic.environment, EnvironmentConfig)
        
        run_id = session_id or str(uuid.uuid4())[:8]
        active_build = build_id or f"build-{sanitize_name(epic_name)}"
        
        if not self.sessions.get_session(run_id):
            self.sessions.start_session(run_id, {"type": "epic", "name": epic.name, "department": self.department, "task_input": epic.description})
        
        existing = self.cards.get_by_build(active_build)
        if existing: self.cards.reset_build(active_build)
        
        for i in epic.issues:
            if not any(ex["id"] == i.id for ex in existing):
                card_data = i.model_dump()
                card_data.update({"session_id": run_id, "build_id": active_build, "sprint": get_eos_sprint(), "status": CardStatus.READY})
                self.cards.save(card_data)

        log_event("session_start", {"epic": epic.name, "run_id": run_id, "build_id": active_build}, workspace=self.workspace)
        await self._traction_loop(active_build, run_id, epic, team, env, driver_steered, target_issue_id)
        
        legacy_transcript = [
            {"step_index": i, "role": t.role, "issue": t.issue_id, "summary": t.content, "note": t.note}
            for i, t in enumerate(self.transcript)
        ]
        self.sessions.complete_session(run_id, "done", legacy_transcript)
        log_event("session_end", {"run_id": run_id}, workspace=self.workspace)
        self.snapshots.record(run_id, {"epic": epic.model_dump(), "team": team.model_dump(), "env": env.model_dump(), "build_id": active_build}, legacy_transcript)

        return legacy_transcript

    async def run_rock(self, rock_name: str, build_id: str = None, session_id: str = None, driver_steered: bool = False, **kwargs) -> Dict:
        rock = self.loader.load_asset("rocks", rock_name, RockConfig)
        sid = session_id or str(uuid.uuid4())[:8]
        active_build = build_id or f"rock-build-{sanitize_name(rock_name)}"
        results = []
        for entry in rock.epics:
            epic_ws = self.workspace / entry["epic"]
            sub_pipeline = ExecutionPipeline(epic_ws, entry["department"])
            res = await sub_pipeline.run_epic(entry["epic"], build_id=active_build, session_id=sid, driver_steered=driver_steered)
            results.append({"epic": entry["epic"], "transcript": res})
        return {"rock": rock.name, "results": results}

    def _find_parent_epic(self, issue_id: str) -> tuple[EpicConfig | None, str | None, IssueConfig | None]:
        for ename in self.loader.list_assets("epics"):
            try:
                epic = self.loader.load_asset("epics", ename, EpicConfig)
                for i in epic.issues:
                    if i.id == issue_id: return epic, ename, i
            except: continue
        return None, None, None

    async def _traction_loop(self, active_build: str, run_id: str, epic: EpicConfig, team: TeamConfig, env: EnvironmentConfig, driver_steered: bool, target_issue_id: str = None):
        policy = create_session_policy(str(self.workspace), epic.references)
        toolbox = ToolBox(policy, str(self.workspace), epic.references)
        tool_map = get_tool_map(toolbox)
        
        from orket.orchestration.models import ModelSelector
        model_selector = ModelSelector(organization=self.org)

        while True:
            backlog = self.cards.get_by_build(active_build)
            ready = [i for i in backlog if i["status"] == CardStatus.READY]
            if target_issue_id: ready = [i for i in ready if i["id"] == target_issue_id]
            if not ready: break
            
            issue = ready[0]
            issue_id, seat_name = issue["id"], issue["seat"]
            
            # 1. Resolve Seat and Atomic Roles
            seat = team.seats.get(sanitize_name(seat_name))
            if not seat:
                self.cards.update_status(issue_id, CardStatus.CANCELED)
                continue

            role_objects = []
            for r_name in seat.roles:
                try:
                    role_objects.append(self.loader.load_asset("roles", r_name, RoleConfig))
                except Exception as e:
                    print(f"  [WARN] Failed to load atomic role '{r_name}': {e}")

            # 2. Select Model for this role
            # Use the primary role (first role in seat) for model selection
            primary_role_name = seat.roles[0] if seat.roles else "coder"
            selected_model = model_selector.select(
                role=primary_role_name,
                department=self.department,
                asset_config=epic
            )
            
            provider = LocalModelProvider(model=selected_model, temperature=env.temperature, timeout=env.timeout)

            prompt_patch = None
            if driver_steered:
                from orket.driver import OrketDriver
                driver = OrketDriver()
                steering_msg = f"Turn {len(self.transcript)}. Issue: {issue['summary']}. Provide tactical directive."
                prompt_patch = f"DRIVER DIRECTIVE: {await driver.process_request(steering_msg)}"

            self.cards.update_status(issue_id, CardStatus.IN_PROGRESS, assignee=seat_name)

            desc = f"Seat: {seat_name}.\nISSUE: {issue['summary']}\nMANDATORY: Use 'write_file' to persist work. One Issue, One Member.\n"
            
            # 3. Inject Notes from previous steps
            relevant_notes = self.notes.get_for_role(seat_name, len(self.transcript))
            if relevant_notes:
                desc += "\n[INTER-AGENT NOTES]\n"
                for n in relevant_notes:
                    desc += f"- From {n.from_role}: {n.content}\n"

            # 4. Inject Prompts from Roles
            for ro in role_objects:
                if ro.prompt:
                    desc += f"\n[{ro.name.upper()} GUIDELINES]\n{ro.prompt}\n"

            # Inject Organization context
            if self.org:
                desc += f"\n[ORGANIZATION: {self.org.name}]\nEthos: {self.org.ethos}\nBranding Rules: {', '.join(self.org.branding.design_dos)}\n"

            # Aggregate tools
            tools = {}
            for ro in role_objects:
                for tn in ro.tools:
                    if tn in tool_map:
                        tools[tn] = tool_map[tn]
            
            print(f"  [ORKESTRATE] {seat_name} -> {issue_id} (Model: {selected_model})")
            
            turn_count = 0
            while turn_count < 5:
                agent = Agent(seat_name, desc, tools, provider, prompt_patch=prompt_patch)
                turn: ExecutionTurn = await agent.run(
                    task={"description": f"{epic.description}\n\nTask: {issue['summary']}"},
                    context={"session_id": run_id, "issue_id": issue_id, "workspace": str(self.workspace), "role": seat_name},
                    workspace=self.workspace,
                    transcript=[{"role": t.role, "summary": t.content} for t in self.transcript]
                )
                
                if turn.thought:
                    log_event("reasoning", {"thought": turn.thought, "role": seat_name}, self.workspace, role=seat_name)
                
                # Log usage for metrics
                from orket.logging import log_model_usage
                log_model_usage(seat_name, selected_model, turn.raw, turn_count, epic.name, self.workspace)

                # --- HIGH-LEVEL NARRATIVE MESSAGE ---
                log_event("member_message", {
                    "role": seat_name,
                    "issue_id": issue_id,
                    "content": turn.content,
                    "thought": turn.thought,
                    "tools": [tc.tool for t_idx, tc in enumerate(turn.tool_calls)]
                }, self.workspace, role=seat_name)

                # Capture Notes from output (Heuristic: Look for JSON blocks or explicit note fields)
                try:
                    # If the content is JSON, look for 'notes' field
                    if turn.content.strip().startswith("{"):
                        data = json.loads(turn.content)
                        if "notes" in data:
                            for note_text in data["notes"]:
                                self.notes.add(Note(from_role=seat_name, content=note_text, step_index=len(self.transcript)))
                except:
                    pass

                self.transcript.append(turn)
                current_db_issue = self.cards.get_by_id(issue_id)

                if turn.tool_calls and current_db_issue["status"] == CardStatus.IN_PROGRESS:
                    turn_count += 1
                    continue
                else:
                    if current_db_issue["status"] == CardStatus.IN_PROGRESS:
                        self.cards.update_status(issue_id, CardStatus.CODE_REVIEW)
                    break

# Shims
async def orchestrate_card(card_id: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_card(card_id, **kwargs)

async def orchestrate(epic_name: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_epic(epic_name, **kwargs)

async def orchestrate_rock(rock_name: str, workspace: Path, **kwargs) -> Dict[str, Any]:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_rock(rock_name, **kwargs)