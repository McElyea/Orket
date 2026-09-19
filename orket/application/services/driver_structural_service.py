"""Application authority for captured model-proposed structural writes."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.driver_resource_store import DriverResourceStore
from orket.application.services.driver_resource_values import normalize_epic
from orket.core.policies.card_acceptance_admission import ModelAcceptanceDefinitionRejected, validate_model_card_payload
from orket.logging import log_event


@dataclass(frozen=True)
class DriverStructuralService:
    model_root: Path
    workspace_root: Path

    async def execute(self, plan: dict) -> str:
        captured = deepcopy(plan)
        model, workspace = Path(self.model_root), Path(self.workspace_root)
        if not model.is_absolute() or not workspace.is_absolute():
            raise ValueError("DRIVER_ROOTS_MUST_BE_ABSOLUTE")
        return await run_owned_thread(
            lambda: _StructuralCommand(DriverResourceStore(model), workspace).execute(captured),
            label="driver-structural-command")


class _StructuralCommand:
    def __init__(self, store, workspace_root):
        self.store, self.workspace_root = store, workspace_root

    def execute(self, plan):
        action = plan.get("action")
        new_asset = plan.get("new_asset", {})
        workspace_path = self.workspace_root
        try:
            validate_model_card_payload(new_asset)
        except ModelAcceptanceDefinitionRejected as exc:
            log_event("driver_process_failed", {"error": str(exc), "action": action,
                       "failure_kind": "acceptance_admission"}, workspace_path, role="DRIVER")
            return f"Error: {exc}. Model proposals cannot declare completion acceptance; no assets were written."
        suggested_dept = plan.get("suggested_department", "core")
        dept_root = self.store.path(suggested_dept)

        if not dept_root.exists():
            dept_root = self.store.path("core")
        suggested_dept = dept_root.name

        handlers = {"create_issue": self._create_issue, "create_epic": self._create_epic,
                    "create_rock": self._create_rock}
        if action not in handlers:
            return "No structural action taken."
        with self.store.guard():
            return handlers[action](plan, new_asset, dept_root, suggested_dept, workspace_path)

    def _create_issue(self, plan, new_asset, dept_root, suggested_dept, workspace_path):
        parent_epic = plan.get("target_parent")
        path = self.store.path(str(dept_root / "epics" / f"{parent_epic}.json"))
        if not path.exists():
            path = self.store.path(str(self.store.path("core") / "epics" / f"{parent_epic}.json"))

        if path.exists():
            epic_data, migrated = normalize_epic(self.store.read(path))
            issue_entry = {
                "summary": new_asset.get("summary", "New Task"),
                "seat": new_asset.get("seat", "senior_developer"),
                "priority": new_asset.get("priority", "Medium"),
                "note": new_asset.get("note", ""),
            }
            epic_data["issues"].append(issue_entry)
            self.store.write(path, epic_data)
            log_event(
                "create_issue",
                {"epic": parent_epic, "summary": issue_entry["summary"]},
                workspace_path,
                role="DRIVER",
            )
            migration_note = " Legacy epic child key was normalized to 'issues'." if migrated else ""
            return (
                f"Added issue '{issue_entry['summary']}' to Epic "
                f"'{parent_epic}' in {path.parent.parent.name}.{migration_note}"
            )
        return f"Error: Target epic {parent_epic} not found in core or {suggested_dept}."


    def _create_epic(self, plan, new_asset, dept_root, suggested_dept, workspace_path):
        epic_name = new_asset.get("name", "new_epic")
        epic_path = self.store.path(str(dept_root / "epics" / f"{epic_name}.json"))

        parent_rock = plan.get("target_parent")
        rock_path = self.store.path(str(dept_root / "rocks" / f"{parent_rock}.json"))
        if not rock_path.exists():
            rock_path = self.store.path(str(self.store.path("core") / "rocks" / f"{parent_rock}.json"))

        if not parent_rock or not rock_path.exists():
            parent_rock = f"Rock-Nomination-{epic_name}"
            nom_path = self.store.path(str(dept_root / "rocks" / f"{parent_rock}.json"))
            rock_data = {
                "name": parent_rock,
                "description": f"Strategic parent for {new_asset.get('description', 'new initiative')}",
                "owner_department": suggested_dept,
                "epics": [{"epic": epic_name, "department": suggested_dept}],
            }
            self.store.write(epic_path, new_asset)
            self.store.write(nom_path, rock_data)
            log_event(
                "create_epic",
                {"name": epic_name, "rock": parent_rock, "dept": suggested_dept},
                workspace_path,
                role="DRIVER",
            )
            log_event("create_rock", {"name": parent_rock, "dept": suggested_dept}, workspace_path, role="DRIVER")
            return f"Created Epic '{epic_name}' and nominated new parent Rock '{parent_rock}' in {suggested_dept}."
        rock_data = self.store.read(rock_path)
        if "epics" not in rock_data:
            rock_data["epics"] = []
        rock_data["epics"].append({"epic": epic_name, "department": suggested_dept})
        self.store.write(epic_path, new_asset)
        self.store.write(rock_path, rock_data)
        log_event(
            "create_epic",
            {"name": epic_name, "rock": parent_rock, "dept": suggested_dept},
            workspace_path,
            role="DRIVER",
        )
        return (
            f"Created Epic '{epic_name}' and linked to existing Rock "
            f"'{parent_rock}' in {rock_path.parent.parent.name}."
        )


    def _create_rock(self, plan, new_asset, dept_root, suggested_dept, workspace_path):
        rock_name = new_asset.get("name", "new_rock")
        path = self.store.path(str(dept_root / "rocks" / f"{rock_name}.json"))
        self.store.write(path, new_asset)
        log_event("create_rock", {"name": rock_name, "dept": suggested_dept}, workspace_path, role="DRIVER")
        return f"Nominated new Rock: '{rock_name}' in {suggested_dept}."
