import asyncio
from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import require_sync_context, run_owned_thread
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_result_lifetime import open_runtime_owner
from orket.application.services.runtime_result_projection import require_runtime_success
from orket.core.critical_path import CriticalPathEngine
from orket.logging import log_event
from orket.runtime import ConfigLoader, ExecutionPipeline
from orket.schema import EpicConfig, OrganizationConfig


class OrganizationLoop:
    def __init__(
        self, organization_path: Path = Path("config/organization.json"), *,
        construction_inputs: RuntimeConstructionInputs | None = None,
    ) -> None:
        require_sync_context(code="E_ORGANIZATION_LOOP_ASYNC_CREATE_REQUIRED")
        self.construction_inputs = construction_inputs or RuntimeConstructionInputs.capture()
        self.project_root = self.construction_inputs.invocation_root
        self.workspace = self.project_root / "workspace/default"
        self.org_path = self.project_root / organization_path
        self.fs = AsyncFileTools(self.project_root)
        if not self.org_path.exists():
            self.org_path = self.project_root / "model/organization.json"
        self.org = self._load_org()
        self._departments = tuple(self.org.departments)
        self.running = False

    @classmethod
    async def create(
        cls, organization_path: Path = Path("config/organization.json"), *,
        construction_inputs: RuntimeConstructionInputs | None = None,
    ) -> "OrganizationLoop":
        inputs = construction_inputs if construction_inputs is not None else await RuntimeConstructionInputs.capture_async()
        return await run_owned_thread(partial(cls, organization_path, construction_inputs=inputs),
                                      label="organization-loop-construction")

    def _load_org(self) -> OrganizationConfig:
        return OrganizationConfig.model_validate_json(self.fs.read_file_sync(str(self.org_path)))

    async def run_forever(self) -> None:
        self.running = True
        try:
            log_event("organization_loop_started", {"mode": "critical_path"}, workspace=self.workspace)
            while self.running:
                next_card = await run_owned_thread(self._find_next_critical_card, label="organization-card-scan")
                if next_card:
                    log_event(
                        "organization_loop_execute_card",
                        {"card_id": next_card["id"], "department": next_card["dept"]},
                        workspace=self.workspace,
                    )
                    construct = partial(ExecutionPipeline, self.workspace, str(next_card["dept"]),
                                        construction_inputs=self.construction_inputs)
                    async with open_runtime_owner(construct, label="organization-card-construction") as pipeline:
                        require_runtime_success(await pipeline.run_card(str(next_card["id"])))
                else:
                    await asyncio.sleep(10)
                await asyncio.sleep(0)
        finally:
            self.running = False

    def _find_next_critical_card(self) -> dict[str, str | int] | None:
        """Finds the most critical READY card across all departments."""
        candidates: list[dict[str, str | int]] = []

        for dept in self._departments:
            loader = ConfigLoader(self.project_root, dept, environment=self.construction_inputs.environment)
            for epic_name in loader.list_assets("epics"):
                try:
                    epic = loader.load_asset("epics", epic_name, EpicConfig)
                    # Use Engine to get sorted IDs
                    priority_ids = CriticalPathEngine.get_priority_queue(epic.issues)

                    if priority_ids:
                        top_id = priority_ids[0]
                        # Fetch original issue for priority check
                        issue = next(i for i in epic.issues if i.id == top_id)
                        candidates.append(
                            {
                                "id": top_id,
                                "weight": len(priority_ids),  # Simplified global weight
                                "priority": str(issue.priority),
                                "dept": dept,
                            }
                        )
                except (FileNotFoundError, ValueError, StopIteration) as e:
                    # Log skip for visibility but continue scan
                    log_event(
                        "organization_loop_skip_epic",
                        {"epic": epic_name, "department": dept, "error": str(e)},
                        workspace=self.workspace,
                    )
                    continue

        if not candidates:
            return None

        # Sort by Weight (Length of remaining critical path) then Priority
        candidates.sort(key=lambda x: (-int(x["weight"]), -float(x["priority"])))

        return candidates[0]
