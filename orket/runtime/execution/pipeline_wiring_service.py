from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import Any

from orket.application.services.decision_node_registry import build_decision_node_registry
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.runtime_paths import (
    durable_root,
    resolve_control_plane_db_path,
    resolve_sandbox_lifecycle_db_path,
    resolve_webhook_db_path,
)


class PipelineWiringService:
    """Explicit owner for execution-pipeline subordinate runtime construction."""

    def __init__(self, construction_inputs: RuntimeConstructionInputs | None = None) -> None:
        self.construction_inputs = construction_inputs

    def _selected_inputs(self, explicit: RuntimeConstructionInputs | None) -> RuntimeConstructionInputs | None:
        return explicit if explicit is not None else self.construction_inputs

    def create_sandbox_orchestrator(
        self, workspace: Any, organization: Any, *, construction_inputs: RuntimeConstructionInputs | None = None,
    ) -> Any:
        from orket.services.sandbox_orchestrator import SandboxOrchestrator

        inputs = self._selected_inputs(construction_inputs)
        if inputs is None:
            return SandboxOrchestrator(workspace, organization=organization)
        return SandboxOrchestrator(workspace, organization=organization, environment=inputs.environment,
            terminal_evidence_root=durable_root(invocation_root=inputs.invocation_root,
                                               environment=inputs.environment) / "sandbox_terminal_evidence",
            decision_nodes=build_decision_node_registry(environment=inputs.environment),
            lifecycle_db_path=resolve_sandbox_lifecycle_db_path(invocation_root=inputs.invocation_root,
                                                               environment=inputs.environment),
            control_plane_db_path=str(resolve_control_plane_db_path(invocation_root=inputs.invocation_root,
                                                                    environment=inputs.environment)))

    def create_webhook_database(self, *, construction_inputs: RuntimeConstructionInputs | None = None) -> Any:
        from orket.adapters.vcs.webhook_db import WebhookDatabase

        inputs = self._selected_inputs(construction_inputs)
        return WebhookDatabase(resolve_webhook_db_path(invocation_root=inputs.invocation_root,
            environment=inputs.environment)) if inputs is not None else WebhookDatabase()

    def create_bug_fix_manager(
        self, organization: Any, webhook_db: Any, *, workspace: Any, now_utc: Callable[[], datetime],
    ) -> Any:
        from orket.application.services.bug_fix_phase_manager import BugFixPhaseManager

        return BugFixPhaseManager(
            organization_config=organization.process_rules if organization else {},
            db=webhook_db,
            workspace=workspace,
            now_utc=now_utc,
        )

    def create_orchestrator(
        self,
        *,
        workspace: Any,
        async_cards: Any,
        snapshots: Any,
        org: Any,
        config_root: Any,
        db_path: str,
        loader: Any,
        sandbox_orchestrator: Any,
        card_completion: Any = None,
        control_plane_clock: Callable[[], str],
        construction_inputs: RuntimeConstructionInputs | None = None,
    ) -> Any:
        from orket.application.workflows.orchestrator import Orchestrator

        inputs = self._selected_inputs(construction_inputs)
        return Orchestrator(
            workspace=workspace,
            async_cards=async_cards,
            snapshots=snapshots,
            org=org,
            config_root=config_root,
            db_path=db_path,
            loader=loader,
            sandbox_orchestrator=sandbox_orchestrator,
            card_completion=card_completion,
            control_plane_clock=control_plane_clock,
            environment=inputs.environment if inputs is not None else None,
        )

    async def prepare_sub_pipeline(self, *, parent_pipeline: Any, epic_workspace: Any, department: str) -> Callable[[], Any]:
        pipeline_type = parent_pipeline.__class__
        arguments = dict(db_path=parent_pipeline.db_path, config_root=parent_pipeline.config_root,
                         decision_nodes=parent_pipeline.decision_nodes, runtime_inputs=parent_pipeline.runtime_inputs)
        inputs = parent_pipeline.runtime_context.construction_inputs
        inputs = inputs if inputs is not None else await RuntimeConstructionInputs.capture_async()
        return partial(
            pipeline_type,
            epic_workspace,
            department,
            **arguments,
            pipeline_wiring_service=self,
            construction_inputs=inputs,
        )
