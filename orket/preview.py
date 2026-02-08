from pathlib import Path
from typing import Dict, Any, List, Optional
import json
from orket.orket import ConfigLoader
from orket.schema import RockConfig, EpicConfig, IssueConfig, TeamConfig, EnvironmentConfig, SkillConfig, DialectConfig
from orket.agents.agent import Agent
from orket.utils import sanitize_name

class PreviewBuilder:
    """
    Compiles a 'flat' view of a Rock, Epic, or individual Issue, 
    including fully-resolved prompts for every member.
    """
    def __init__(self, model_root: Path = Path("model")):
        self.model_root = model_root

    async def build_issue_preview(self, issue_id: str, epic_name: str, department: str = "core") -> Dict[str, Any]:
        loader = ConfigLoader(self.model_root, department)
        epic = loader.load_asset("epics", epic_name, EpicConfig)
        team = loader.load_asset("teams", epic.team, TeamConfig)
        env = loader.load_asset("environments", epic.environment, EnvironmentConfig)
        
        issue = next((i for i in epic.issues if i.id == issue_id), None)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found in epic {epic_name}")

        # Use Agent logic to load configs
        from orket.llm import LocalModelProvider
        mock_provider = type("MockProvider", (), {"model": env.model})
        
        # Determine next member for warm handoff instructions
        idx = next((i for i, iss in enumerate(epic.issues) if iss.id == issue_id), -1)
        next_member = epic.issues[idx+1].seat if idx != -1 and idx + 1 < len(epic.issues) else None
        
        agent = Agent(issue.seat, "Preview Mode", {}, mock_provider, next_member=next_member)
        compiled_prompt = agent._build_system_prompt()

        return {
            "type": "issue",
            "id": issue.id,
            "parent_epic": epic_name,
            "display_name": issue.name,
            "assigned_to": issue.seat,
            "priority": issue.priority,
            "environment": env.model,
            "compiled_system_prompt": compiled_prompt
        }

    async def build_epic_preview(self, epic_name: str, department: str = "core") -> Dict[str, Any]:
        loader = ConfigLoader(self.model_root, department)
        epic = loader.load_asset("epics", epic_name, EpicConfig)
        team = loader.load_asset("teams", epic.team, TeamConfig)
        env = loader.load_asset("environments", epic.environment, EnvironmentConfig)
        
        preview = {
            "type": "epic",
            "id": epic_name,
            "display_name": epic.name,
            "description": epic.description,
            "team": epic.team,
            "environment": env.model,
            "sequencing": []
        }

        # Simulate the traction loop to build prompts
        for idx, issue in enumerate(epic.issues):
            next_member = epic.issues[idx+1].seat if idx + 1 < len(epic.issues) else None
            
            from orket.llm import LocalModelProvider
            mock_provider = type("MockProvider", (), {"model": env.model})
            
            agent = Agent(issue.seat, "Preview Mode", {}, mock_provider, next_member=next_member)
            compiled_prompt = agent._build_system_prompt()
            
            preview["sequencing"].append({
                "step": idx + 1,
                "issue_id": issue.id,
                "summary": issue.name,
                "assigned_to": issue.seat,
                "priority": issue.priority,
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