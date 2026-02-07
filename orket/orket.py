# orket/orket.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from orket.llm import LocalModelProvider
from orket.logging import log_event
from orket.conductor import Conductor, ManualConductor, SessionView
from orket.agents.agent_factory import build_band_agents
from orket.tools import _policy
from orket.settings import get_setting
from orket.schema import ProjectConfig, TeamConfig, EnvironmentConfig, SequenceConfig


# ---------------------------------------------------------------------------
# Configuration Loader (Department-Aware)
# ---------------------------------------------------------------------------

class ConfigLoader:
    def __init__(self, model_root: Path, department: str = "core"):
        self.model_root = model_root
        self.department = department
        self.dept_path = model_root / department

    def list_projects(self) -> List[str]:
        path = self.dept_path / "projects"
        return [p.stem for p in path.glob("*.json")]

    def list_teams(self) -> List[str]:
        path = self.dept_path / "teams"
        return [p.stem for p in path.glob("*.json")]

    def list_environments(self) -> List[str]:
        path = self.dept_path / "environments"
        return [p.stem for p in path.glob("*.json")]

    def list_sequences(self) -> List[str]:
        path = self.dept_path / "sequences"
        return [p.stem for p in path.glob("*.json")]

    def load_project(self, name: str) -> ProjectConfig:
        path = self.dept_path / "projects" / f"{name}.json"
        return ProjectConfig.model_validate_json(path.read_text(encoding="utf-8"))

    def load_team(self, name: str) -> TeamConfig:
        path = self.dept_path / "teams" / f"{name}.json"
        return TeamConfig.model_validate_json(path.read_text(encoding="utf-8"))

    def load_environment(self, name: str) -> EnvironmentConfig:
        path = self.dept_path / "environments" / f"{name}.json"
        return EnvironmentConfig.model_validate_json(path.read_text(encoding="utf-8"))

    def load_sequence(self, name: str) -> SequenceConfig:
        path = self.dept_path / "sequences" / f"{name}.json"
        return SequenceConfig.model_validate_json(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def orchestrate(
    project_name: str,
    workspace: Path,
    department: str = "core",
    model_override: Optional[str] = None,
    task_override: Optional[str] = None,
    interactive_conductor: bool = False,
) -> Any:
    """
    Asynchronous orchestration entry point.
    """
    workspace = workspace.resolve()
    model_root = Path("model").resolve()
    loader = ConfigLoader(model_root, department)

    # 1. Load the Project
    project = loader.load_project(project_name)
    
    # 2. Load dependencies
    team = loader.load_team(project.team)
    sequence = loader.load_sequence(project.sequence)
    env = loader.load_environment(project.environment)
    
    # 3. Handle Overrides
    final_model = model_override or env.model
    final_task = task_override or project.example_task or "No task provided."

    _policy().add_workspace(str(workspace))

    provider = LocalModelProvider(
        model=final_model, 
        temperature=env.temperature, 
        seed=env.seed
    )
    conductor: Conductor = ManualConductor() if interactive_conductor else Conductor()

    agents = build_band_agents(team, provider)

    conductor.log_session_models(
        team=team,
        provider=provider,
        workspace=workspace,
        project_name=project.name,
    )

    transcript: List[Dict[str, Any]] = []
    notes: Dict[str, Any] = {}

    log_event(
        "session_start",
        {
            "department": department,
            "project": project.name,
            "team": team.name,
            "sequence": sequence.name,
            "model": provider.model,
            "task": final_task[:100] + "..." if len(final_task) > 100 else final_task
        },
        workspace=workspace,
    )

    for idx, step in enumerate(sequence.steps):
        role_name = step.role
        session_view = SessionView(
            flow_name=project.name,
            step_index=idx,
            transcript=transcript,
            role=role_name,
            notes=notes,
        )

        step_dict = step.model_dump()
        adjust = conductor.before_step(step_dict, session_view)

        if adjust.skip_role:
            log_event("step_skipped", {"role": role_name, "step_index": idx}, workspace=workspace, role=role_name)
            continue

        log_event("step_start", {"role": role_name, "step_index": idx, "model": provider.model}, workspace=workspace, role=role_name)

        agent = agents[role_name]
        agent.apply_prompt_patch(adjust.prompt_patch)

        # AWAIT the async agent run
        response = await agent.run(
            task={"description": final_task},
            context={
                "step_index": idx,
                "workspace": str(workspace),
                "project_name": project.name,
                "notes": notes,
            },
            workspace=workspace,
            transcript=transcript,
        )

        if "NOTES_UPDATE:" in response.content:
            try:
                parts = response.content.split("NOTES_UPDATE:")
                update_str = parts[1].splitlines()[0].strip()
                update_data = json.loads(update_str)
                notes.update(update_data)
            except:
                pass

        log_event("step_end", {"role": role_name, "step_index": idx, "output_preview": response.content[:100]}, workspace=workspace, role=role_name)

        transcript.append({
            "step_index": idx,
            "role": role_name,
            "note": response.note,
            "summary": response.content,
        })

        conductor.after_step(step_dict, session_view)

    log_event("session_end", {"project": project.name}, workspace=workspace)

    return transcript
