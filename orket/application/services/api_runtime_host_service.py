from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_input_service import RuntimeInputService


class ApiRuntimeHostService:
    """Explicit owner for API-facing runtime object construction and session ids."""

    def __init__(self, project_root: Path, *, runtime_inputs: RuntimeInputService | None = None,
                 environment: Mapping[str, str] | None = None,
                 construction_inputs: RuntimeConstructionInputs | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.runtime_inputs = runtime_inputs or RuntimeInputService()
        self.construction_inputs = construction_inputs
        self.environment = MappingProxyType(dict(os.environ if environment is None else environment))

    def create_session_id(self) -> str:
        return self.runtime_inputs.create_session_id()

    def create_flow_authoring_service(self) -> Any:
        from orket.application.services.flow_runtime_service import build_flow_authoring_service

        return build_flow_authoring_service(self.project_root, self.runtime_inputs)

    def utc_now_iso(self) -> str:
        return self.runtime_inputs.utc_now_iso()

    async def create_preview_builder(self, model_root: Path | None = None) -> Any:
        from orket.application.services.preview_service import PreviewBuilder

        return await run_owned_thread(
            lambda: PreviewBuilder(model_root or self.project_root / "model", environment=self.environment),
            label="api-preview-bootstrap",
        )

    async def create_chat_driver(self) -> Any:
        from orket.driver import OrketDriver

        return await OrketDriver.create(project_root=self.project_root, environment=self.environment)

    async def close_chat_driver(self, driver: Any) -> None:
        await run_owned_io(driver.close, label="api-chat-driver-close", preserve_failure=True)

    def create_execution_pipeline(self, workspace_root: Path | None = None) -> Any:
        from orket.runtime.execution_pipeline import ExecutionPipeline

        return ExecutionPipeline(
            workspace_root or self.project_root / "workspace" / "default",
            config_root=self.project_root,
            runtime_inputs=self.runtime_inputs,
            construction_inputs=self.construction_inputs,
        )

    def create_engine(self, workspace_root: Path | None = None) -> Any:
        from orket.orchestration.engine import OrchestrationEngine

        return OrchestrationEngine(
            workspace_root or self.project_root / "workspace" / "default",
            config_root=self.project_root,
            runtime_inputs=self.runtime_inputs,
            construction_inputs=self.construction_inputs,
        )

    def create_file_tools(self, project_root: Path | None = None) -> Any:
        from orket.adapters.storage.async_file_tools import AsyncFileTools

        return AsyncFileTools(project_root or self.project_root)

    def create_member_metrics_reader(self) -> Any:
        from orket.logging import get_member_metrics

        return get_member_metrics
