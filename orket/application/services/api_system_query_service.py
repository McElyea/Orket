"""Application authority for API filesystem and board observations."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.api_workspace_reader import ApiWorkspaceReader
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.board import get_board_hierarchy_async
from orket.core.contracts.eos_calendar import EosSprintBaseline
from orket.time_utils import configured_timezone


class ApiSystemQueryService:
    def __init__(
        self, project_root: Path, *, environment: Mapping[str, str], runtime_inputs: RuntimeInputService,
    ) -> None:
        self.reader = ApiWorkspaceReader(project_root)
        self.calendar = EosSprintBaseline.from_environment(environment)
        self.timezone = configured_timezone(environment.get("ORKET_TIMEZONE") or "UTC")
        self.runtime_inputs = runtime_inputs

    def local_now(self) -> datetime:
        return self.runtime_inputs.utc_now().astimezone(self.timezone)

    def current_sprint(self, now: datetime) -> str:
        return self.calendar.current_sprint(now)

    async def explorer(self, path: str, strategy: Any) -> dict[str, Any]:
        entries = await self.reader.directory(path)
        if entries is None:
            return {"items": [], "path": path}
        items = [{"name": entry.name, "is_dir": entry.is_dir, "ext": entry.suffix}
                 for entry in entries if strategy.include_explorer_entry(entry.name)]
        return {"items": strategy.sort_explorer_items(items), "path": path}

    async def member_metrics_workspace(self, session_id: str) -> Path:
        return await self.reader.member_metrics_workspace(session_id)

    async def member_metrics(self, session_id: str, read: Callable[[Path], Any]) -> Any:
        workspace = await self.member_metrics_workspace(session_id)
        return await run_owned_thread(partial(read, workspace), label="api-member-metrics")

    async def system_board(self, department: str) -> Any:
        return await get_board_hierarchy_async(department, project_root=self.reader.project_root)
