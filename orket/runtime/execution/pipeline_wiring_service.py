from __future__ import annotations

from typing import Any


class PipelineWiringService:
    """Explicit owner for execution-pipeline subordinate runtime construction."""

    def create_sandbox_orchestrator(self, workspace: Any, organization: Any) -> Any:
        from orket.services.sandbox_orchestrator import SandboxOrchestrator

        return SandboxOrchestrator(workspace, organization=organization)

    def create_webhook_database(self) -> Any:
        from orket.adapters.vcs.webhook_db import WebhookDatabase

        return WebhookDatabase()

    def create_bug_fix_manager(self, organization: Any, webhook_db: Any) -> Any:
        from orket.core.domain.bug_fix_phase import BugFixPhaseManager

        return BugFixPhaseManager(
            organization_config=organization.process_rules if organization else {},
            db=webhook_db,
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
    ) -> Any:
        from orket.application.workflows.orchestrator import Orchestrator

        return Orchestrator(
            workspace=workspace,
            async_cards=async_cards,
            snapshots=snapshots,
            org=org,
            config_root=config_root,
            db_path=db_path,
            loader=loader,
            sandbox_orchestrator=sandbox_orchestrator,
        )

    def create_sub_pipeline(self, *, parent_pipeline: Any, epic_workspace: Any, department: str) -> Any:
        return parent_pipeline.__class__(
            epic_workspace,
            department,
            db_path=parent_pipeline.db_path,
            config_root=parent_pipeline.config_root,
            decision_nodes=parent_pipeline.decision_nodes,
            runtime_inputs=parent_pipeline.runtime_inputs,
            pipeline_wiring_service=self,
        )
