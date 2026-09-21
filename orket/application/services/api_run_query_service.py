"""Application-owned diagnostic reads and pure response projections for API runs."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from orket.adapters.storage.api_run_log_reader import ApiRunLogReader
from orket.core.contracts import run_observation_projection as projection


class ApiRunQueryService:
    def __init__(self, project_root: Path) -> None:
        self.reader = ApiRunLogReader(project_root)

    async def token_summary(self, session_id: str) -> dict[str, Any]:
        return projection.token_summary(await self.reader.records(session_id), session_id)

    async def replay_turns(self, session_id: str, role: str | None) -> list[dict[str, Any]]:
        return projection.replay_turns(await self.reader.records(session_id), session_id, role)

    async def handoffs(self, session_id: str, index_by_id: Mapping[str, int]) -> list[dict[str, Any]]:
        admitted_index = dict(index_by_id)
        records = await self.reader.records(session_id, run_first=True)
        return projection.handoff_edges(records, session_id, admitted_index)

    async def run_path(self, session_id: str) -> Path:
        return await self.reader.run_path(session_id)

    async def logs(self, *, session_id: str | None, event: str | None, role: str | None,
                   start_dt: datetime | None, end_dt: datetime | None, limit: int, offset: int) -> dict[str, Any]:
        records = await self.reader.records(session_id)
        return projection.log_page(records, session_id=session_id, event=event, role=role,
                                   start_dt=start_dt, end_dt=end_dt, limit=limit, offset=offset)
