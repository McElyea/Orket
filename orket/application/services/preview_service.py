from __future__ import annotations

import os
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.agents.agent import Agent
from orket.application.services.model_selection_service import ModelSelectionService
from orket.exceptions import CardNotFound
from orket.logging import log_event
from orket.runtime import ConfigLoader
from orket.schema import EpicConfig, OrganizationConfig, RockConfig, TeamConfig
from orket.utils import sanitize_name


@dataclass(frozen=True)
class PreviewModelProvider:
    model: str

    async def complete(
        self,
        messages: list[dict[str, str]],
        runtime_context: dict[str, Any] | None = None,
    ) -> Any:
        raise NotImplementedError("PreviewModelProvider does not execute completions.")


class PreviewBuilder:
    """
    Compiles a 'flat' view of a Rock, Epic, or individual Issue,
    including fully-resolved prompts for every member.
    """

    def __init__(self, model_root: Path = Path("model"), *, environment: Mapping[str, str] | None = None):
        self.project_root = (model_root.parent if model_root.name == "model" else model_root).resolve()
        self.model_root = self.project_root / "model"
        self.fs = AsyncFileTools(self.project_root)
        self.model_selection = ModelSelectionService(environment=os.environ if environment is None else environment)

    async def _loader(self, department: str) -> ConfigLoader:
        return await run_owned_thread(partial(ConfigLoader, self.project_root, department), label="preview-loader")

    async def _organization(self) -> OrganizationConfig | None:
        try:
            content = await run_owned_thread(partial(self.fs.read_file_sync, str(self.model_root / "organization.json")),
                                             label="preview-organization")
            return OrganizationConfig.model_validate_json(content)
        except (ValueError, FileNotFoundError) as exc:
            await run_owned_thread(partial(log_event, "preview_org_config_missing", {"error": str(exc)},
                                          workspace=self.project_root / "workspace/default"), label="preview-config-observation")
            return None

    async def _asset(self, loader: ConfigLoader, category: str, name: str, model_type: Any) -> Any:
        return await run_owned_io(partial(loader.load_asset_async, category, name, model_type), label="preview-asset")

    async def _get_compiled_prompt(
        self, seat_name: str, issue_summary: str, epic: EpicConfig, team: TeamConfig, department: str
    ) -> str:
        epic, team = deepcopy(epic), deepcopy(team)
        loader = await self._loader(department)
        seat = team.seats.get(sanitize_name(seat_name))
        if not seat:
            return "Seat not found."

        # Load Atomic Roles
        from orket.schema import RoleConfig

        role_objects = []
        for r_name in seat.roles:
            try:
                role_objects.append(await self._asset(loader, "roles", r_name, RoleConfig))
            except (FileNotFoundError, ValueError, CardNotFound) as e:
                await run_owned_thread(partial(
                    log_event, "preview_role_asset_missing",
                    {"role": r_name, "department": department, "error": str(e)},
                    workspace=self.project_root / "workspace/default",
                ), label="preview-role-observation")

        # 2. Select Model
        organization = await self._organization()
        selection = await self.model_selection.prepare(organization)
        role = seat.roles[0] if seat.roles else "coder"
        asset_models = (getattr(epic, "params", {}) or {}).get("model_overrides", {})
        selected_model = selection.select(role, asset_model=str(asset_models.get(role, ""))).final_model

        desc = f"Seat: {seat_name}.\nISSUE: {issue_summary}\n"

        # Inject Notes placeholder for preview
        desc += "\n[INTER-AGENT NOTES]\n- Note from Previous Agent: Placeholder for preview...\n"

        for ro in role_objects:
            if ro.prompt:
                desc += f"\n[{ro.name.upper()} GUIDELINES]\n{ro.prompt}\n"

        if organization:
            desc += (
                f"\n[ORGANIZATION: {organization.name}]\n"
                f"Ethos: {organization.ethos}\n"
                f"Branding Rules: {', '.join(organization.branding.design_dos)}\n"
            )

        config_root = self.model_root.parent if self.model_root.name == "model" else self.model_root
        build_agent = partial(Agent,
            seat_name,
            desc,
            {},
            PreviewModelProvider(model=selected_model),
            strict_config=False,
            config_root=config_root,
        )
        return await run_owned_thread(lambda: build_agent().get_compiled_prompt(), label="preview-prompt-compilation")

    async def build_issue_preview(self, issue_id: str, epic_name: str, department: str = "core") -> dict[str, Any]:
        loader = await self._loader(department)
        epic = await self._asset(loader, "epics", epic_name, EpicConfig)
        team = await self._asset(loader, "teams", epic.team, TeamConfig)

        # 1. Try to find by ID
        issue = next((i for i in epic.issues if i.id == issue_id), None)

        # 2. Fallback: Try to find by name (in case of volatile IDs)
        if not issue:
            issue = next((i for i in epic.issues if i.name == issue_id), None)

        if not issue:
            raise ValueError(f"Issue {issue_id} not found in epic {epic_name}")

        compiled_prompt = await self._get_compiled_prompt(issue.seat, issue.name, epic, team, department)

        return {
            "type": "issue",
            "id": issue.id,
            "display_name": issue.name,
            "assigned_to": issue.seat,
            "compiled_system_prompt": compiled_prompt,
        }

    async def build_epic_preview(self, epic_name: str, department: str = "core") -> dict[str, Any]:
        loader = await self._loader(department)
        epic = await self._asset(loader, "epics", epic_name, EpicConfig)
        team = await self._asset(loader, "teams", epic.team, TeamConfig)

        preview = {"type": "epic", "id": epic_name, "display_name": epic.name, "sequencing": []}

        for idx, issue in enumerate(epic.issues):
            compiled_prompt = await self._get_compiled_prompt(issue.seat, issue.name, epic, team, department)
            preview["sequencing"].append(
                {
                    "step": idx + 1,
                    "issue_id": issue.id,
                    "summary": issue.name,
                    "assigned_to": issue.seat,
                    "compiled_system_prompt": compiled_prompt,
                }
            )

        return preview

    async def build_rock_preview(self, rock_name: str, department: str = "core") -> dict[str, Any]:
        loader = await self._loader(department)
        rock = await self._asset(loader, "rocks", rock_name, RockConfig)

        preview = {
            "type": "rock",
            "id": rock_name,
            "display_name": rock.name,
            "description": rock.description,
            "milestone_tasks": rock.task,
            "epics": [],
        }

        for entry in rock.epics:
            epic_preview = await self.build_epic_preview(entry["epic"], entry["department"])
            preview["epics"].append(epic_preview)

        return preview
