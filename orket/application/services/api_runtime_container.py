from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from orket.application.interactions.commands import InteractionCommands
from orket.application.services.api_event_service import ApiEventService
from orket.application.services.application_runtime_lifetime import (
    ApplicationRuntimeLifetime,
    RequestAdmissionClosed,
    close_owned_resource,
)
from orket.application.services.interaction_cancellation_service import InteractionCancellationService


class ApiRequestAdmissionClosed(RequestAdmissionClosed):
    """The API application stopped admitting request invocations before dispatch."""


@dataclass
class ApiRuntimeContainer(ApplicationRuntimeLifetime):
    """Application-owned runtime graph with the shared invocation lifetime."""

    _runtime_name: ClassVar[str] = "API"
    _admission_error: ClassVar[type[RequestAdmissionClosed]] = ApiRequestAdmissionClosed
    project_root: Path
    api_runtime_node: Any
    runtime_state: Any
    api_runtime_host: Any
    engine: Any
    events: ApiEventService = field(init=False)
    authentication: Any | None = None
    system_queries: Any | None = None
    run_queries: Any | None = None
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
    model_selection: Any | None = None
    governed_agent_runtime: Any | None = None

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).resolve()
        self.events = ApiEventService(self.project_root)

    def interaction_cancellation(self) -> InteractionCancellationService:
        return InteractionCancellationService(
            manager=self.interaction_manager, publication=self.engine.control_plane_publication,
            utc_now=self.api_runtime_host.utc_now_iso,
        )

    def interactions(self) -> InteractionCommands:
        return InteractionCommands(self.interaction_manager, self.extension_manager, self, self.project_root)

    async def _close_final_resource(self) -> None:
        await close_owned_resource(self.engine)
