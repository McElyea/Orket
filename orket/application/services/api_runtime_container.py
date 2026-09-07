from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ApiRuntimeContainer:
    """Application-owned runtime owners and lifecycle for one API app."""

    project_root: Path
    api_runtime_node: Any
    runtime_state: Any
    api_runtime_host: Any
    engine: Any
    stream_bus: Any | None = None
    interaction_manager: Any | None = None
    extension_manager: Any | None = None
    extension_runtime_service: Any | None = None
    _background_tasks: set[asyncio.Task[Any]] = field(default_factory=set, repr=False)
    _closed: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).resolve()

    @property
    def active_background_task_count(self) -> int:
        return sum(1 for task in self._background_tasks if not task.done())

    @property
    def closed(self) -> bool:
        return self._closed

    def track_background_task(self, task: asyncio.Task[Any]) -> None:
        if self._closed:
            task.cancel()
            raise RuntimeError("API runtime container is closed.")
        self._background_tasks.add(task)

    def release_background_task(self, task: asyncio.Task[Any]) -> None:
        self._background_tasks.discard(task)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        tasks = [task for task in self._background_tasks if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._background_tasks.clear()

        close = getattr(self.engine, "aclose", None) or getattr(self.engine, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result
