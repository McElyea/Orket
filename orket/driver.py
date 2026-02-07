import json
from pathlib import Path
from typing import Dict, Any, List
from orket.llm import LocalModelProvider
from orket.orket import ConfigLoader
from orket.schema import RockConfig, EpicConfig, IssueConfig

class OrketDriver:
    """
    The Driver is the high-level intent parser and resource manager.
    It manages Rocks, Epics, Issues, and Team Selection.
    """
    def __init__(self, model: str = "qwen2.5-coder:7b"):
        self.provider = LocalModelProvider(model=model, temperature=0.1)
        self.model_root = Path("model")

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

        # 2. Ask the model to decide the structural change + Team selection
        system_prompt = """You are the Orket Driver.
Your job is to architect the project board AND select the best resources.

Rules:
1. Identify the BEST Team/Department for this work from the inventory.
2. If complex, create a new Epic. ALWAYS include:
   - "team": (choose from inventory, usually 'enterprise')
   - "environment": (usually 'standard')
   - "issues": (generate at least 2-3 initial operational Cards following iDesign: Manager, Engine, or Accessor tasks)
3. If no Rock fits, nominate a new Rock.

YOU MUST RESPOND WITH VALID JSON matching the Orket Schema.
Example for create_epic:
{
  "action": "create_epic",
  "reasoning": "...",
  "target_parent": "rock_name",
  "new_asset": {
    "name": "auth_manager",
    "description": "...",
    "team": "enterprise",
    "environment": "standard",
    "issues": [
      { "summary": "Define AuthManager interface", "seat": "lead_architect", "priority": "High" },
      { "summary": "Implement BCrypt password engine", "seat": "backend_specialist", "priority": "High" }
    ]
  }
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
            plan = json.loads(text[start:end+1])
            
            return await self.execute_plan(plan)
        except Exception as e:
            return f"Driver failed to process request: {str(e)}"

    async def execute_plan(self, plan: Dict[str, Any]) -> str:
        action = plan.get("action")
        new_asset = plan.get("new_asset", {})
        reasoning = plan.get("reasoning", "No reasoning provided.")
        
        if action == "assign_team":
            team = plan.get("suggested_team")
            dept = plan.get("suggested_department")
            return f"Resource Selection: Switching to Team '{team}' in '{dept}'.\nReason: {reasoning}"

        res = await self._execute_structural_change(plan)
        return f"{res}\n\nStrategic Insight: {reasoning}"

    async def _execute_structural_change(self, plan: Dict[str, Any]) -> str:
        action = plan.get("action")
        new_asset = plan.get("new_asset", {})
        core_root = self.model_root / "core"
        
        if action == "create_issue":
            parent_epic = plan.get("target_parent")
            path = core_root / "epics" / f"{parent_epic}.json"
            if path.exists():
                epic_data = json.loads(path.read_text(encoding="utf-8"))
                if "issues" not in epic_data: epic_data["issues"] = []
                epic_data["issues"].append(new_asset)
                path.write_text(json.dumps(epic_data, indent=2), encoding="utf-8")
                return f"Added issue '{new_asset.get('summary')}' to Epic '{parent_epic}'."
            return f"Error: Target epic {parent_epic} not found."

        elif action == "create_epic":
            epic_name = new_asset.get("name", "new_epic")
            path = core_root / "epics" / f"{epic_name}.json"
            path.write_text(json.dumps(new_asset, indent=2), encoding="utf-8")
            
            parent_rock = plan.get("target_parent")
            if not parent_rock or not (core_root / "rocks" / f"{parent_rock}.json").exists():
                # Nominate new Rock if none found or fits
                parent_rock = f"Rock-Nomination-{epic_name}"
                rock_data = {
                    "name": parent_rock,
                    "description": f"Strategic parent for {new_asset.get('description', 'new initiative')}",
                    "owner_department": "core",
                    "epics": [{"epic": epic_name, "department": "core"}]
                }
                (core_root / "rocks" / f"{parent_rock}.json").write_text(json.dumps(rock_data, indent=2), encoding="utf-8")
                return f"Created Epic '{epic_name}' and nominated new parent Rock '{parent_rock}'."
            else:
                rock_path = core_root / "rocks" / f"{parent_rock}.json"
                rock_data = json.loads(rock_path.read_text(encoding="utf-8"))
                rock_data["epics"].append({"epic": epic_name, "department": "core"})
                rock_path.write_text(json.dumps(rock_data, indent=2), encoding="utf-8")
                return f"Created Epic '{epic_name}' and linked to existing Rock '{parent_rock}'."

        elif action == "create_rock":
            rock_name = new_asset.get("name", "new_rock")
            path = core_root / "rocks" / f"{rock_name}.json"
            path.write_text(json.dumps(new_asset, indent=2), encoding="utf-8")
            return f"Nominated new Rock: '{rock_name}'."

        return "No structural action taken."