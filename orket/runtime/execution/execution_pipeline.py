from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.async_repositories import (
    AsyncSessionRepository,
    AsyncSnapshotRepository,
    AsyncSuccessRepository,
)
from orket.adapters.vcs.gitea_artifact_exporter import GiteaArtifactExporter
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.application.services.cards_epic_control_plane_service import CardsEpicControlPlaneService
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.logging import log_event
from orket.orchestration.orchestration_config import OrchestrationConfig
from orket.runtime.config_loader import ConfigLoader
from orket.runtime.epic_run_orchestrator import EpicRunOrchestrator
from orket.runtime.epic_run_types import EpicRunCallbacks
from orket.runtime.execution_pipeline_artifact_provenance import ExecutionPipelineArtifactProvenanceMixin
from orket.runtime.execution_pipeline_card_dispatch import ExecutionPipelineCardDispatchMixin
from orket.runtime.execution_pipeline_ledger_events import ExecutionPipelineLedgerEventsMixin
from orket.runtime.execution_pipeline_resume import ExecutionPipelineResumeMixin
from orket.runtime.execution_pipeline_run_summary import ExecutionPipelineRunSummaryMixin
from orket.runtime.execution_pipeline_runtime_artifacts import ExecutionPipelineRuntimeArtifactsMixin
from orket.runtime.execution.pipeline_wiring_service import PipelineWiringService
from orket.runtime.run_ledger_factory import build_run_ledger_repository
from orket.runtime.runtime_context import OrketRuntimeContext
from orket.runtime.workload_shell import SharedWorkloadShell
from orket.settings import load_user_settings


class ExecutionPipeline(
    ExecutionPipelineCardDispatchMixin,
    ExecutionPipelineResumeMixin,
    ExecutionPipelineRunSummaryMixin,
    ExecutionPipelineRuntimeArtifactsMixin,
    ExecutionPipelineArtifactProvenanceMixin,
    ExecutionPipelineLedgerEventsMixin,
):
    """
    The central engine for Orket Unit execution.
    Load -> Validate -> Plan -> Execute -> Persist -> Report
    """

    def __init__(
        self,
        workspace: Path,
        department: str = "core",
        db_path: str | None = None,
        config_root: Path | None = None,
        cards_repo: AsyncCardRepository | None = None,
        sessions_repo: AsyncSessionRepository | None = None,
        snapshots_repo: AsyncSnapshotRepository | None = None,
        success_repo: AsyncSuccessRepository | None = None,
        run_ledger_repo: Any | None = None,
        decision_nodes: DecisionNodeRegistry | None = None,
        runtime_context: OrketRuntimeContext | None = None,
        runtime_inputs: RuntimeInputService | None = None,
        pipeline_wiring_service: PipelineWiringService | None = None,
    ):
        from orket.orchestration.notes import NoteStore

        runtime_nodes = decision_nodes or DecisionNodeRegistry()
        self.runtime_context = runtime_context or OrketRuntimeContext.from_env(
            workspace_root=workspace,
            department=department,
            db_path=db_path,
            config_root=config_root,
            cards_repo=cards_repo,
            sessions_repo=sessions_repo,
            snapshots_repo=snapshots_repo,
            success_repo=success_repo,
            run_ledger_repo=run_ledger_repo,
            decision_nodes=runtime_nodes,
            config_loader_factory=ConfigLoader,
            config_loader_kwargs={"decision_nodes": runtime_nodes},
            run_ledger_factory=build_run_ledger_repository,
            telemetry_sink=self._emit_run_ledger_telemetry,
        )
        self.workspace = self.runtime_context.workspace_root
        self.department = self.runtime_context.department
        self.decision_nodes = self.runtime_context.decision_nodes
        self.config_root = self.runtime_context.config_root
        self.loader = self.runtime_context.loader
        self.db_path = self.runtime_context.db_path
        self.org = self.runtime_context.org
        self.orchestration_config = self.runtime_context.orchestration_config
        self.user_settings = dict(self.runtime_context.user_settings)
        self.state_backend_mode = self.runtime_context.state_backend_mode
        self.run_ledger_mode = self.runtime_context.run_ledger_mode
        self.gitea_state_pilot_enabled = self.runtime_context.gitea_state_pilot_enabled
        self.runtime_inputs = runtime_inputs or RuntimeInputService()
        self.execution_runtime_node = self.decision_nodes.resolve_execution_runtime(self.org)
        self.pipeline_wiring_service = pipeline_wiring_service or PipelineWiringService()

        self.async_cards = self.runtime_context.cards_repo
        self.sessions = self.runtime_context.sessions_repo
        self.snapshots = self.runtime_context.snapshots_repo
        self.success = self.runtime_context.success_repo
        self.run_ledger = self.runtime_context.run_ledger
        self.artifact_exporter = GiteaArtifactExporter(self.workspace)

        self.notes = NoteStore()
        self.transcript: list[dict[str, Any]] = []
        self.sandbox_orchestrator = self.pipeline_wiring_service.create_sandbox_orchestrator(
            workspace=self.workspace,
            organization=self.org,
        )
        self.webhook_db = self.pipeline_wiring_service.create_webhook_database()
        self.bug_fix_manager = self.pipeline_wiring_service.create_bug_fix_manager(
            organization=self.org,
            webhook_db=self.webhook_db,
        )
        self.orchestrator = self.pipeline_wiring_service.create_orchestrator(
            workspace=self.workspace,
            async_cards=self.async_cards,
            snapshots=self.snapshots,
            org=self.org,
            config_root=self.config_root,
            db_path=self.db_path,
            loader=self.loader,
            sandbox_orchestrator=self.sandbox_orchestrator,
        )
        self.orchestrator.run_ledger = self.run_ledger
        self.cards_epic_control_plane = CardsEpicControlPlaneService(
            execution_repository=self.orchestrator.control_plane_execution_repository,
            publication=self.orchestrator.control_plane_publication,
        )
        self.workload_shell = SharedWorkloadShell()
        self._initialize_lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            await self.runtime_context.initialize()
            self._initialized = True

    def _process_rules_value(self, key: str) -> str:
        process_rules = getattr(self.org, "process_rules", None) if self.org else None
        if process_rules is None:
            return ""
        if isinstance(process_rules, dict) or hasattr(process_rules, "get"):
            value = process_rules.get(key, "")
        else:
            value = getattr(process_rules, key, "")
        return str(value or "").strip()

    def _resolve_state_backend_mode(self) -> str:
        user_settings = getattr(self, "user_settings", None)
        if not isinstance(user_settings, dict):
            loaded = load_user_settings()
            user_settings = loaded if isinstance(loaded, dict) else {}
        return OrchestrationConfig(self.org).resolve_state_backend_mode(user_settings=user_settings)

    def _resolve_run_ledger_mode(self) -> str:
        user_settings = getattr(self, "user_settings", None)
        if not isinstance(user_settings, dict):
            loaded = load_user_settings()
            user_settings = loaded if isinstance(loaded, dict) else {}
        return OrchestrationConfig(self.org).resolve_run_ledger_mode(user_settings=user_settings)

    def _validate_state_backend_mode(self) -> None:
        self.orchestration_config.validate_state_backend_mode(
            self.state_backend_mode,
            self.gitea_state_pilot_enabled,
        )

    async def _emit_run_ledger_telemetry(self, payload: dict[str, Any]) -> None:
        log_event(
            "run_ledger_telemetry",
            {
                "run_ledger_mode": self.run_ledger_mode,
                **dict(payload or {}),
            },
            workspace=self.workspace,
        )

    def _resolve_gitea_state_pilot_enabled(self) -> bool:
        user_settings = getattr(self, "user_settings", None)
        if not isinstance(user_settings, dict):
            loaded = load_user_settings()
            user_settings = loaded if isinstance(loaded, dict) else {}
        return OrchestrationConfig(self.org).resolve_gitea_state_pilot_enabled(user_settings=user_settings)

    def _build_epic_run_orchestrator(self) -> EpicRunOrchestrator:
        return EpicRunOrchestrator(
            workspace=self.workspace,
            department=self.department,
            organization=self.org,
            runtime_input_service=self.runtime_inputs,
            execution_runtime_node=self.execution_runtime_node,
            pipeline_wiring_service=self.pipeline_wiring_service,
            cards_repo=self.async_cards,
            sessions_repo=self.sessions,
            snapshots_repo=self.snapshots,
            success_repo=self.success,
            run_ledger=self.run_ledger,
            cards_epic_control_plane=self.cards_epic_control_plane,
            loader=self.loader,
            orchestrator=self.orchestrator,
            workload_shell=self.workload_shell,
            callbacks=EpicRunCallbacks(
                resolve_idesign_mode=self._resolve_idesign_mode,
                resume_stalled_issues=self._resume_stalled_issues,
                resume_target_issue_if_existing=self._resume_target_issue_if_existing,
                run_artifact_refs=self._run_artifact_refs,
                build_packet1_facts=self._build_packet1_facts,
                materialize_protocol_receipts=self._materialize_protocol_receipts,
                materialize_run_summary=self._materialize_run_summary,
                export_run_artifacts=self._export_run_artifacts,
                set_transcript=lambda transcript: setattr(self, "transcript", transcript),
            ),
        )


async def orchestrate_card(card_id: str, workspace: Path, **kwargs: Any) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_card(card_id, **kwargs)


async def orchestrate(epic_name: str, workspace: Path, **kwargs: Any) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_card(epic_name, **kwargs)
