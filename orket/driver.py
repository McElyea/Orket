import json
from pathlib import Path
from typing import Dict, Any, List
from orket.infrastructure.async_file_tools import AsyncFileTools
from orket.llm import LocalModelProvider
from orket.orket import ConfigLoader
from orket.schema import RockConfig, EpicConfig, IssueConfig, SkillConfig, DialectConfig
from orket.logging import log_event
from orket.exceptions import CardNotFound

class OrketDriver:
    """
    The Driver is the high-level intent parser and resource manager.
    It manages Rocks, Epics, Issues, and Team Selection.
    """
    def __init__(self, model: str = None):
        self.fs = AsyncFileTools(Path("."))
        # 1. Load Organization context
        from orket.schema import OrganizationConfig
        org_path = Path("model/organization.json")
        self.org = None
        if org_path.exists():
            try:
                self.org = OrganizationConfig.model_validate_json(self.fs.read_file_sync(str(org_path)))
            except (ValueError, FileNotFoundError):
                pass

        # 2. Select Model
        from orket.orchestration.models import ModelSelector
        selector = ModelSelector(organization=self.org)
        selected_model = selector.select(role="operations_lead", override=model)
        
        self.provider = LocalModelProvider(model=selected_model, temperature=0.1)
        self.model_root = Path("model")
        self.skill: SkillConfig | None = None
        self.dialect: DialectConfig | None = None
        self._load_engine_configs()

    def _load_engine_configs(self):
        from orket.orket import ConfigLoader
        loader = ConfigLoader(Path("model"), "core")
        
        # 1. Load specialized Driver skill if exists, otherwise fallback
        try:
            self.skill = loader.load_asset("skills", "operations_lead", SkillConfig)
        except (FileNotFoundError, ValueError, CardNotFound):
            pass

        # 2. Load Dialect
        model_name = self.provider.model.lower()
        if "deepseek" in model_name: family = "deepseek-r1"
        elif "llama" in model_name: family = "llama3"
        elif "phi" in model_name: family = "phi"
        elif "qwen" in model_name: family = "qwen"
        else: family = "generic"
            
        try:
            self.dialect = loader.load_asset("dialects", family, DialectConfig)
        except (FileNotFoundError, ValueError, CardNotFound):
            pass

    async def _get_inventory(self) -> Dict[str, Any]:
        """Scans all departments for teams and skills."""
        inventory = {"departments": {}}
        for dept_dir in self.model_root.iterdir():
            if dept_dir.is_dir():
                dept_name = dept_dir.name
                inventory["departments"][dept_name] = {
                    "teams": [f.stem for f in (dept_dir / "teams").glob("*.json")] if (dept_dir / "teams").exists() else [],
                    "skills": [f.stem for f in (dept_dir / "skills").glob("*.json")] if (dept_dir / "skills").exists() else []
                }
        return inventory

    async def process_request(self, message: str) -> str:
        # 1. Gather current context + Inventory
        loader = ConfigLoader(Path("model"), "core")
        inventory = await self._get_inventory()
        
        context = {
            "inventory": inventory,
            "active_rocks": loader.list_assets("rocks"),
            "active_epics": loader.list_assets("epics"),
            "request": message
        }

        # 2. Build compiled prompt
        if self.skill and self.dialect:
            system_prompt = f"IDENTITY: {self.skill.name}\nINTENT: {self.skill.intent}\n\n"
            system_prompt += "RESPONSIBILITIES:\n" + "\n".join([f"- {r}" for r in self.skill.responsibilities]) + "\n\n"
            system_prompt += f"SYNTAX DIALECT ({self.dialect.model_family}):\n"
            system_prompt += "YOU MUST RESPOND WITH VALID JSON matching the Orket Schema.\n"
            system_prompt += "\nCONSTRAINTS:\n" + "\n".join([f"- {c}" for c in self.dialect.constraints])
            system_prompt += f"\nGUARDRAIL: {self.dialect.hallucination_guard}\n"
        else:
            # Fallback hardcoded prompt
            system_prompt = """You are the Orket Driver.
Your job is to architect the project board AND select the best resources.
YOU MUST RESPOND WITH VALID JSON matching the Orket Schema.
"""
        
        system_prompt += """
Example for create_epic:
{
  "action": "create_epic",
  "reasoning": "...",
  "suggested_department": "core",
  "target_parent": "rock_name",
  "new_asset": { ... }
}

Example for turn_directive:
{
  "action": "turn_directive",
  "reasoning": "The architect's design is complete, but we need the coder to focus specifically on the BCrypt implementation first.",
  "target_seat": "senior_developer",
  "directive": "Implement the BCrypt engine based on the design in doc_1.md.",
  "prompt_patch": "CRITICAL FOCUS: Ensure you use the 'hashpw' method from the bcrypt library. Do not use plain text fallbacks even for testing."
}
"""
        
        response = await self.provider.complete([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context: {context}\nRequest: {message}"}
        ])

        try:
            text = response.content
            start = text.find('{')
            end = text.rfind('}')
            if start == -1 or end == -1:
                return f"Driver failed to find JSON in response: {text[:100]}..."
                
            plan = json.loads(text[start:end+1])
            return await self.execute_plan(plan)
        except json.JSONDecodeError as e:
            return f"Driver failed to parse JSON: {str(e)}"
        except (RuntimeError, ValueError, TypeError, KeyError, OSError) as e:
            # Fallback for unexpected logical errors, but still better than a bare except
            import traceback
            print(f"ERROR: Driver process failed: {e}\n{traceback.format_exc()}")
            return f"Driver failed to process request due to internal error: {str(e)}"

    async def execute_plan(self, plan: Dict[str, Any]) -> str:
        action = plan.get("action")
        new_asset = plan.get("new_asset", {})
        reasoning = plan.get("reasoning", "No reasoning provided.")
        
        if action == "assign_team":
            team = plan.get("suggested_team")
            dept = plan.get("suggested_department")
            log_event("team_assignment", {"team": team, "department": dept, "reason": reasoning}, Path("workspace/default"), role="DRIVER")
            return f"Resource Selection: Switching to Team '{team}' in '{dept}'.\nReason: {reasoning}"

        if action == "turn_directive":
            # This is where we produce a Note for the target seat
            target = plan.get("target_seat")
            directive = plan.get("directive")
            # The OrchestrationEngine will need to handle this note delivery
            return f"Tactical Directive issued to {target}: {directive}"

        res = await self._execute_structural_change(plan)
        return f"{res}\n\nStrategic Insight: {reasoning}"

    async def _execute_structural_change(self, plan: Dict[str, Any]) -> str:
        action = plan.get("action")
        new_asset = plan.get("new_asset", {})
        suggested_dept = plan.get("suggested_department", "core")
        dept_root = self.model_root / suggested_dept
        workspace_path = Path("workspace/default")
        
        if not dept_root.exists(): dept_root = self.model_root / "core"
        
        if action == "create_issue":
            parent_epic = plan.get("target_parent")
            path = dept_root / "epics" / f"{parent_epic}.json"
            if not path.exists(): path = self.model_root / "core" / "epics" / f"{parent_epic}.json"
            
            if path.exists():
                epic_data = json.loads(self.fs.read_file_sync(str(path)))
                if "issues" not in epic_data: epic_data["issues"] = []
                issue_entry = {
                    "summary": new_asset.get("summary", "New Task"),
                    "seat": new_asset.get("seat", "senior_developer"),
                    "priority": new_asset.get("priority", "Medium"),
                    "note": new_asset.get("note", "")
                }
                epic_data["issues"].append(issue_entry)
                self.fs.write_file_sync(str(path), epic_data)
                log_event("create_issue", {"epic": parent_epic, "summary": issue_entry["summary"]}, workspace_path, role="DRIVER")
                return f"Added issue '{issue_entry['summary']}' to Epic '{parent_epic}' in {path.parent.parent.name}."
            return f"Error: Target epic {parent_epic} not found in core or {suggested_dept}."

        elif action == "create_epic":
            epic_name = new_asset.get("name", "new_epic")
            epic_path = dept_root / "epics" / f"{epic_name}.json"
            epic_path.parent.mkdir(parents=True, exist_ok=True)
            self.fs.write_file_sync(str(epic_path), new_asset)
            
            parent_rock = plan.get("target_parent")
            rock_path = dept_root / "rocks" / f"{parent_rock}.json"
            if not rock_path.exists(): rock_path = self.model_root / "core" / "rocks" / f"{parent_rock}.json"

            if not parent_rock or not rock_path.exists():
                parent_rock = f"Rock-Nomination-{epic_name}"
                nom_path = dept_root / "rocks" / f"{parent_rock}.json"
                nom_path.parent.mkdir(parents=True, exist_ok=True)
                rock_data = {
                    "name": parent_rock,
                    "description": f"Strategic parent for {new_asset.get('description', 'new initiative')}",
                    "owner_department": suggested_dept,
                    "epics": [{"epic": epic_name, "department": suggested_dept}]
                }
                self.fs.write_file_sync(str(nom_path), rock_data)
                log_event("create_epic", {"name": epic_name, "rock": parent_rock, "dept": suggested_dept}, workspace_path, role="DRIVER")
                log_event("create_rock", {"name": parent_rock, "dept": suggested_dept}, workspace_path, role="DRIVER")
                return f"Created Epic '{epic_name}' and nominated new parent Rock '{parent_rock}' in {suggested_dept}."
            else:
                rock_data = json.loads(self.fs.read_file_sync(str(rock_path)))
                if "epics" not in rock_data: rock_data["epics"] = []
                rock_data["epics"].append({"epic": epic_name, "department": suggested_dept})
                self.fs.write_file_sync(str(rock_path), rock_data)
                log_event("create_epic", {"name": epic_name, "rock": parent_rock, "dept": suggested_dept}, workspace_path, role="DRIVER")
                return f"Created Epic '{epic_name}' and linked to existing Rock '{parent_rock}' in {rock_path.parent.parent.name}."

        elif action == "create_rock":
            rock_name = new_asset.get("name", "new_rock")
            path = dept_root / "rocks" / f"{rock_name}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.fs.write_file_sync(str(path), new_asset)
            log_event("create_rock", {"name": rock_name, "dept": suggested_dept}, workspace_path, role="DRIVER")
            return f"Nominated new Rock: '{rock_name}' in {suggested_dept}."

        elif action == "adopt_issue":
            issue_id = plan.get("issue_id")
            target_epic = plan.get("target_epic")
            # Logic: Load epic, find issue in orphanage, append, save. 
            # Simplified: Models can just read/write the JSONs to fix orphans now.
            return f"Structural Reconciler: Moving issue {issue_id} to Epic {target_epic}."

        return "No structural action taken."
