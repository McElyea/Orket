from pathlib import Path
from typing import Dict, Any, List, Optional
import json
from orket.infrastructure.async_file_tools import AsyncFileTools
from orket.orket import ConfigLoader
from orket.schema import RockConfig, EpicConfig, IssueConfig, TeamConfig, EnvironmentConfig, SkillConfig, DialectConfig
from orket.agents.agent import Agent
from orket.utils import sanitize_name
from orket.exceptions import CardNotFound
from orket.logging import log_event

class PreviewBuilder:
    """
    Compiles a 'flat' view of a Rock, Epic, or individual Issue, 
    including fully-resolved prompts for every member.
    """
    def __init__(self, model_root: Path = Path("model")):
        self.model_root = model_root
        self.fs = AsyncFileTools(Path("."))
        
        # Load Organization
        org_path = model_root / "organization.json"
        self.org = None
        if org_path.exists():
            from orket.schema import OrganizationConfig
            try:
                self.org = OrganizationConfig.model_validate_json(self.fs.read_file_sync(str(org_path)))
            except (ValueError, FileNotFoundError) as e:
                log_event("preview_org_config_missing", {"error": str(e)}, workspace=Path("workspace/default"))
                pass

    async def _get_compiled_prompt(self, seat_name: str, issue_summary: str, epic: EpicConfig, team: TeamConfig, department: str) -> str:
        loader = ConfigLoader(self.model_root, department)
        seat = team.seats.get(sanitize_name(seat_name))
        if not seat: return "Seat not found."

        # Load Atomic Roles
        from orket.schema import RoleConfig
        role_objects = []
        for r_name in seat.roles:
            try:
                role_objects.append(loader.load_asset("roles", r_name, RoleConfig))
            except (FileNotFoundError, ValueError, CardNotFound) as e:
                log_event(
                    "preview_role_asset_missing",
                    {"role": r_name, "department": department, "error": str(e)},
                    workspace=Path("workspace/default"),
                )
                pass

        # 2. Select Model
        from orket.orchestration.models import ModelSelector
        model_selector = ModelSelector(organization=self.org)
        selected_model = model_selector.select(role=seat.roles[0] if seat.roles else "coder", asset_config=epic)

        desc = f"Seat: {seat_name}.\nISSUE: {issue_summary}\n"
        
        # Inject Notes placeholder for preview
        desc += "\n[INTER-AGENT NOTES]\n- Note from Previous Agent: Placeholder for preview...\n"

        for ro in role_objects:
            if ro.prompt:
                desc += f"\n[{ro.name.upper()} GUIDELINES]\n{ro.prompt}\n"

        if self.org:
            desc += f"\n[ORGANIZATION: {self.org.name}]\nEthos: {self.org.ethos}\nBranding Rules: {', '.join(self.org.branding.design_dos)}\n"

        from orket.llm import LocalModelProvider
        mock_provider = type("MockProvider", (), {"model": selected_model})
        agent = Agent(seat_name, desc, {}, mock_provider)
        return agent.get_compiled_prompt()

    async def build_issue_preview(self, issue_id: str, epic_name: str, department: str = "core") -> Dict[str, Any]:
        loader = ConfigLoader(self.model_root, department)
        epic = loader.load_asset("epics", epic_name, EpicConfig)
        team = loader.load_asset("teams", epic.team, TeamConfig)
        
        # 1. Try to find by ID
        issue = next((i for i in epic.issues if i.id == issue_id), None)
        
        # 2. Fallback: Try to find by name (in case of volatile IDs)
        if not issue:
            issue = next((i for i in epic.issues if i.name == issue_id), None)

        if not issue: raise ValueError(f"Issue {issue_id} not found in epic {epic_name}")

        compiled_prompt = await self._get_compiled_prompt(issue.seat, issue.name, epic, team, department)

        return {
            "type": "issue",
            "id": issue.id,
            "display_name": issue.name,
            "assigned_to": issue.seat,
            "compiled_system_prompt": compiled_prompt
        }

    async def build_epic_preview(self, epic_name: str, department: str = "core") -> Dict[str, Any]:
        loader = ConfigLoader(self.model_root, department)
        epic = loader.load_asset("epics", epic_name, EpicConfig)
        team = loader.load_asset("teams", epic.team, TeamConfig)
        
        preview = {
            "type": "epic",
            "id": epic_name,
            "display_name": epic.name,
            "sequencing": []
        }

        for idx, issue in enumerate(epic.issues):
            compiled_prompt = await self._get_compiled_prompt(issue.seat, issue.name, epic, team, department)
            preview["sequencing"].append({
                "step": idx + 1,
                "issue_id": issue.id,
                "summary": issue.name,
                "assigned_to": issue.seat,
                "compiled_system_prompt": compiled_prompt
            })
            
        return preview

    async def build_rock_preview(self, rock_name: str, department: str = "core") -> Dict[str, Any]:
        loader = ConfigLoader(self.model_root, department)
        rock = loader.load_asset("rocks", rock_name, RockConfig)
        
        preview = {
            "type": "rock",
            "id": rock_name,
            "display_name": rock.name,
            "description": rock.description,
            "milestone_tasks": rock.task,
            "epics": []
        }
        
        for entry in rock.epics:
            epic_preview = await self.build_epic_preview(entry["epic"], entry["department"])
            preview["epics"].append(epic_preview)
            
        return preview
