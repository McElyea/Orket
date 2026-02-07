# orket/orket.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Type
import json

from orket.llm import LocalModelProvider
from orket.logging import log_event
from orket.conductor import Conductor, ManualConductor, SessionView
from orket.agents.agent import Agent
from orket.policy import create_session_policy
from orket.tools import ToolBox, get_tool_map, TOOL_TIERS
from orket.schema import EpicConfig, TeamConfig, EnvironmentConfig, RockConfig
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Generic Configuration Loader
# ---------------------------------------------------------------------------

class ConfigLoader:
    def __init__(self, model_root: Path, department: str = "core"):
        self.dept_path = model_root / department

    def list_assets(self, category: str) -> List[str]:
        path = self.dept_path / category
        return [p.stem for p in path.glob("*.json")] if path.exists() else []

    def load_asset(self, category: str, name: str, model_type: Type[BaseModel]) -> Any:
        path = self.dept_path / category / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Asset '{name}' not found in {category}")
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def orchestrate(
    epic_name: str,
    workspace: Path,
    department: str = "core",
    model_override: Optional[str] = None,
    task_override: Optional[str] = None,
    interactive_conductor: bool = False,
    extra_references: List[str] = None,
) -> Any:
    """
    EOS-aligned orchestration with session-scoped security and unified loading.
    """
    workspace = workspace.resolve()
    model_root = Path("model").resolve()
    loader = ConfigLoader(model_root, department)

    # 1. Load Components
    epic = loader.load_asset("epics", epic_name, EpicConfig)
    team = loader.load_asset("teams", epic.team, TeamConfig)
    env = loader.load_asset("environments", epic.environment, EnvironmentConfig)
    
    final_task = task_override or epic.example_task or "No task provided."
    all_refs = epic.references + (extra_references or [])

    # 2. Setup Session Security & Tools
    policy = create_session_policy(str(workspace), all_refs)
    toolbox = ToolBox(policy, str(workspace), all_refs)
    tool_map = get_tool_map(toolbox)

    provider = LocalModelProvider(
        model=model_override or env.model, 
        temperature=env.temperature, 
        seed=env.seed
    )
    conductor: Conductor = ManualConductor() if interactive_conductor else Conductor()

    transcript: List[Dict[str, Any]] = []
    notes: Dict[str, Any] = {}

    log_event("session_start", {"epic": epic.name, "team": team.name}, workspace=workspace)

    # 3. Main Traction Loop
    from orket.hardware import get_current_profile, can_handle_tier
    hw_profile = get_current_profile()

    for iteration in range(epic.iterations):
        for idx, story in enumerate(epic.stories):
            seat_name = story.seat
            seat = team.seats.get(seat_name)
            if not seat: raise ValueError(f"Seat '{seat_name}' not found")
            
            # Aggregate Roles and filter by Hardware
            combined_description = f"Seat: {seat_name}.\n"
            combined_tools = {}
            omitted_tools = []
            
            for role_name in seat.roles:
                role = team.roles.get(role_name)
                if not role: continue
                combined_description += f"\nRole {role.name}: {role.description}\n"
                for t_name in role.tools:
                    if t_name in tool_map:
                        tier = TOOL_TIERS.get(t_name, "utility")
                        if can_handle_tier(tier, hw_profile):
                            combined_tools[t_name] = tool_map[t_name]
                        else:
                            omitted_tools.append(t_name)
            
            if omitted_tools:
                combined_description += f"\n\nDISABLED TOOLS (Hardware): {omitted_tools}."

            session_view = SessionView(epic.name, iteration + 1, idx, seat_name, transcript, notes)
            
            # Governance
            is_first, is_last = (iteration == 0), (iteration == epic.iterations - 1)
            gov = story.governance or "always"
            if (gov == "once" and not is_first) or (gov == "final" and not is_last):
                print(f"  [SKIPPED] {seat_name} (Governance)")
                continue
            
            if conductor.before_step(story.model_dump(), session_view).skip_role:
                continue

            active_model = story.model or model_override or env.model
            print(f"  [RUNNING] R{iteration+1} | {seat_name} ({active_model})...")

            # Provider for this story
            story_provider = LocalModelProvider(active_model, env.temperature, env.seed)
            member = Agent(seat_name, combined_description, combined_tools, story_provider)

            response = await member.run(
                task={"description": final_task},
                context={"story_index": idx, "iteration": iteration + 1, "workspace": str(workspace), "references": all_refs, "notes": notes},
                workspace=workspace,
                transcript=transcript
            )

            # Handle notes
            if "NOTES_UPDATE:" in response.content:
                try: notes.update(json.loads(response.content.split("NOTES_UPDATE:")[1].splitlines()[0]))
                except: pass

            transcript.append({"iteration": iteration + 1, "step_index": idx, "role": seat_name, "note": response.note, "summary": response.content})
            conductor.after_step(story.model_dump(), session_view)

    log_event("session_end", {"epic": epic.name}, workspace=workspace)
    return transcript

async def orchestrate_rock(
    rock_name: str,
    workspace: Path,
    department: str = "core",
    task_override: Optional[str] = None
) -> Dict[str, Any]:
    model_root = Path("model").resolve()
    loader = ConfigLoader(model_root, department)
    rock = loader.load_asset("rocks", rock_name, RockConfig)
    
    results, previous_workspaces = [], []
    for entry in rock.epics:
        dept, epic_name = entry["department"], entry["epic"]
        epic_workspace = workspace / epic_name
        
        transcript = await orchestrate(
            epic_name=epic_name,
            workspace=epic_workspace,
            department=dept,
            task_override=task_override,
            extra_references=rock.references + previous_workspaces
        )
        
        previous_workspaces.append(str(epic_workspace))
        results.append({"epic": epic_name, "dept": dept, "transcript": transcript})

    return {"rock": rock.name, "results": results}