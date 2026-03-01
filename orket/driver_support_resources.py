from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from orket.logging import log_event


class DriverResourceMixin:
    async def _execute_structural_change(self, plan: Dict[str, Any]) -> str:
        action = plan.get("action")
        new_asset = plan.get("new_asset", {})
        suggested_dept = plan.get("suggested_department", "core")
        dept_root = self.model_root / suggested_dept
        workspace_path = Path("workspace/default")

        if not dept_root.exists():
            dept_root = self.model_root / "core"

        if action == "create_issue":
            parent_epic = plan.get("target_parent")
            path = dept_root / "epics" / f"{parent_epic}.json"
            if not path.exists():
                path = self.model_root / "core" / "epics" / f"{parent_epic}.json"

            if path.exists():
                epic_data = json.loads(self.fs.read_file_sync(str(path)))
                if "issues" not in epic_data:
                    epic_data["issues"] = []
                issue_entry = {
                    "summary": new_asset.get("summary", "New Task"),
                    "seat": new_asset.get("seat", "senior_developer"),
                    "priority": new_asset.get("priority", "Medium"),
                    "note": new_asset.get("note", ""),
                }
                epic_data["issues"].append(issue_entry)
                self.fs.write_file_sync(str(path), epic_data)
                log_event("create_issue", {"epic": parent_epic, "summary": issue_entry["summary"]}, workspace_path, role="DRIVER")
                return f"Added issue '{issue_entry['summary']}' to Epic '{parent_epic}' in {path.parent.parent.name}."
            return f"Error: Target epic {parent_epic} not found in core or {suggested_dept}."

        if action == "create_epic":
            epic_name = new_asset.get("name", "new_epic")
            epic_path = dept_root / "epics" / f"{epic_name}.json"
            epic_path.parent.mkdir(parents=True, exist_ok=True)
            self.fs.write_file_sync(str(epic_path), new_asset)

            parent_rock = plan.get("target_parent")
            rock_path = dept_root / "rocks" / f"{parent_rock}.json"
            if not rock_path.exists():
                rock_path = self.model_root / "core" / "rocks" / f"{parent_rock}.json"

            if not parent_rock or not rock_path.exists():
                parent_rock = f"Rock-Nomination-{epic_name}"
                nom_path = dept_root / "rocks" / f"{parent_rock}.json"
                nom_path.parent.mkdir(parents=True, exist_ok=True)
                rock_data = {
                    "name": parent_rock,
                    "description": f"Strategic parent for {new_asset.get('description', 'new initiative')}",
                    "owner_department": suggested_dept,
                    "epics": [{"epic": epic_name, "department": suggested_dept}],
                }
                self.fs.write_file_sync(str(nom_path), rock_data)
                log_event("create_epic", {"name": epic_name, "rock": parent_rock, "dept": suggested_dept}, workspace_path, role="DRIVER")
                log_event("create_rock", {"name": parent_rock, "dept": suggested_dept}, workspace_path, role="DRIVER")
                return f"Created Epic '{epic_name}' and nominated new parent Rock '{parent_rock}' in {suggested_dept}."
            rock_data = json.loads(self.fs.read_file_sync(str(rock_path)))
            if "epics" not in rock_data:
                rock_data["epics"] = []
            rock_data["epics"].append({"epic": epic_name, "department": suggested_dept})
            self.fs.write_file_sync(str(rock_path), rock_data)
            log_event("create_epic", {"name": epic_name, "rock": parent_rock, "dept": suggested_dept}, workspace_path, role="DRIVER")
            return f"Created Epic '{epic_name}' and linked to existing Rock '{parent_rock}' in {rock_path.parent.parent.name}."

        if action == "create_rock":
            rock_name = new_asset.get("name", "new_rock")
            path = dept_root / "rocks" / f"{rock_name}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.fs.write_file_sync(str(path), new_asset)
            log_event("create_rock", {"name": rock_name, "dept": suggested_dept}, workspace_path, role="DRIVER")
            return f"Nominated new Rock: '{rock_name}' in {suggested_dept}."

        if action == "adopt_issue":
            issue_id = plan.get("issue_id")
            target_epic = plan.get("target_epic")
            return f"Structural Reconciler: Moving issue {issue_id} to Epic {target_epic}."

        return "No structural action taken."

    def _list_cards_for_epic(self, epic_name: str, department: str) -> str:
        path = self._find_asset_path("epic", epic_name, department)
        if path is None or not path.exists():
            return f"Epic '{epic_name}' not found in {department}."
        epic_data = json.loads(self.fs.read_file_sync(str(path)))
        cards = list(epic_data.get("cards") or epic_data.get("issues") or [])
        if not cards:
            return f"Epic '{epic_name}' has no cards."
        lines = [f"Cards in {epic_name} ({len(cards)}):"]
        for idx, card in enumerate(cards, start=1):
            summary = str(card.get("summary") or card.get("name") or "Untitled")
            seat = str(card.get("seat") or "unspecified")
            priority = str(card.get("priority") or "n/a")
            lines.append(f"{idx}. [{seat}] p={priority} {summary}")
        return "\n".join(lines)

    def _resource_dir(self, resource: str, department: str) -> Path | None:
        normalized = resource.strip().lower()
        aliases = {
            "team": "teams",
            "teams": "teams",
            "environment": "environments",
            "environments": "environments",
            "epic": "epics",
            "epics": "epics",
            "rock": "rocks",
            "rocks": "rocks",
            "role": "roles",
            "roles": "roles",
            "dialect": "dialects",
            "dialects": "dialects",
            "skill": "skills",
            "skills": "skills",
            "contract": "contracts",
            "contracts": "contracts",
            "artifact": "artifacts",
            "artifacts": "artifacts",
        }
        folder = aliases.get(normalized)
        if not folder:
            return None
        return self.model_root / department / folder

    def _find_asset_path(self, resource: str, name: str, department: str | None = None) -> Path | None:
        search_departments = [department] if department else sorted([p.name for p in self.model_root.iterdir() if p.is_dir()])
        for dept in search_departments:
            resource_dir = self._resource_dir(resource, dept)
            if resource_dir is None:
                continue
            candidate = resource_dir / f"{name}.json"
            if candidate.exists():
                return candidate
        return None

    def _slug_name(self, value: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_") or "unnamed"

    def _team_template(self, name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "description": f"Team '{name}' generated by Operator CLI.",
            "roles": {
                "coder": {
                    "name": "coder",
                    "description": "Software Engineer role focusing on implementation.",
                    "tools": ["read_file", "write_file", "list_directory", "add_issue_comment", "get_issue_context", "update_issue_status"],
                },
                "code_reviewer": {
                    "name": "code_reviewer",
                    "description": "Code reviewer role for governance and quality review.",
                    "tools": ["read_file", "list_directory", "add_issue_comment", "get_issue_context", "update_issue_status"],
                },
            },
            "seats": {
                "coder": {"name": "Coder", "roles": ["coder"]},
                "code_reviewer": {"name": "Code Reviewer", "roles": ["code_reviewer"]},
                "integrity_guard": {"name": "Integrity Guard", "roles": ["integrity_guard"]},
            },
        }

    def _environment_template(self, name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "description": f"Environment '{name}' generated by Operator CLI.",
            "model": "qwen3-coder:latest",
            "temperature": 0.2,
            "seed": 42,
            "params": {},
        }

    def _epic_template(self, name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "description": f"Epic '{name}' generated by Operator CLI.",
            "team": "standard",
            "environment": "standard",
            "cards": [],
        }

    def _rock_template(self, name: str, department: str) -> Dict[str, Any]:
        rock_id = f"{self._slug_name(name).upper()}-ROCK"
        return {
            "id": rock_id,
            "name": name,
            "description": f"Rock '{name}' generated by Operator CLI.",
            "status": "active",
            "owner_department": department,
            "epics": [],
        }
