from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.application.services.runtime_input_service import RuntimeInputService


class ApiRuntimeHostService:
    """Explicit owner for API-facing runtime object construction and session ids."""

    def __init__(self, project_root: Path, *, runtime_inputs: RuntimeInputService | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.runtime_inputs = runtime_inputs or RuntimeInputService()

    def create_session_id(self) -> str:
        return self.runtime_inputs.create_session_id()

    def utc_now_iso(self) -> str:
        return self.runtime_inputs.utc_now_iso()

    def create_preview_builder(self, model_root: Path | None = None) -> Any:
        from orket.preview import PreviewBuilder

        return PreviewBuilder(model_root or self.project_root / "model")

    def create_chat_driver(self) -> Any:
        from orket.driver import OrketDriver

        return OrketDriver()

    def create_execution_pipeline(self, workspace_root: Path | None = None) -> Any:
        from orket.runtime.execution_pipeline import ExecutionPipeline

        return ExecutionPipeline(
            workspace_root or self.project_root / "workspace" / "default",
            runtime_inputs=self.runtime_inputs,
        )

    def create_engine(self, workspace_root: Path | None = None) -> Any:
        from orket.orchestration.engine import OrchestrationEngine

        return OrchestrationEngine(
            workspace_root or self.project_root / "workspace" / "default",
            runtime_inputs=self.runtime_inputs,
        )

    def create_file_tools(self, project_root: Path | None = None) -> Any:
        from orket.adapters.storage.async_file_tools import AsyncFileTools

        return AsyncFileTools(project_root or self.project_root)

    def create_member_metrics_reader(self) -> Any:
        from orket.logging import get_member_metrics

        return get_member_metrics
