from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


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
    outward_run_store: Any | None = None
    outward_run_event_store: Any | None = None
    outward_approval_store: Any | None = None
    outward_run_service: Any | None = None
    outward_approval_service: Any | None = None
    outward_run_execution_service: Any | None = None
    outward_run_inspection_service: Any | None = None
    outward_ledger_service: Any | None = None
    model_selector_factory: Any | None = None
    governed_agent_runtime: Any | None = None
    _background_tasks: set[asyncio.Task[Any]] = field(default_factory=set, repr=False)
    _owned_resources: list[Any] = field(default_factory=list, repr=False)
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

    def register_owned_resource(self, resource: Any) -> None:
        if self._closed:
            raise RuntimeError("API runtime container is closed.")
        if resource not in self._owned_resources:
            self._owned_resources.append(resource)

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

        errors: list[Exception] = []
        for resource in reversed(self._owned_resources):
            try:
                await _close_resource(resource)
            except Exception as exc:  # lifecycle boundary must continue closing peers
                LOGGER.exception("API-owned resource teardown failed", extra={"resource_type": type(resource).__name__})
                errors.append(exc)
        self._owned_resources.clear()
        try:
            await _close_resource(self.engine)
        except Exception as exc:  # lifecycle boundary reports after all close attempts
            LOGGER.exception("API engine teardown failed")
            errors.append(exc)
        if errors:
            raise RuntimeError(f"API runtime teardown failed for {len(errors)} resource(s).") from errors[0]


async def _close_resource(resource: Any) -> None:
    close = getattr(resource, "aclose", None) or getattr(resource, "close", None)
    if callable(close):
        result = close()
        if inspect.isawaitable(result):
            await result
