"""Per-application event publication with captured inputs and retained worker lifetime."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.logging import log_event


@dataclass(frozen=True)
class ApiEventService:
    project_root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_root", Path(self.project_root).resolve())

    async def emit(self, name: str, payload: dict[str, Any]) -> None:
        # Calling the logging adapter off-loop selects its synchronous write path.
        # Retain that write through interruption instead of enqueueing unowned work.
        operation = partial(log_event, name, deepcopy(payload), self.project_root)
        await run_owned_thread(operation, label="api-event-publication")
