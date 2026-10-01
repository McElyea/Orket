from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_pending_gate_repository import AsyncPendingGateRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.application.services import orchestrator_runtime_policy as orchestrator_policy
from orket.application.services import orchestrator_team_policy
from orket.application.services.card_completion_service import CardCompletionService
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.decision_context_service import capture_loop_policy_inputs
from orket.application.services.decision_node_registry import build_decision_node_registry
from orket.application.services.model_client_factory import ModelClientFactory
from orket.application.services.orchestrator_issue_control_plane_service import (
    OrchestratorIssueControlPlaneService,
)
from orket.application.services.orchestrator_issue_transitions import (
    apply_issue_transition_locally,
    resolve_transition_wait_reason,
    validate_issue_transition,
)
from orket.application.services.orchestrator_scheduler_control_plane_service import (
    OrchestratorSchedulerControlPlaneService,
)
from orket.application.services.orchestrator_support_services import OrchestratorSupportServices
from orket.application.services.orchestrator_team_replan import TeamReplanScheduler
from orket.application.services.runtime_policy_inputs import ArchitecturePolicySnapshot
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)
from orket.core.contracts.card_completion_commit import SUCCESSFUL_CARD_STATUSES, CardCompletionRequest
from orket.core.contracts.repositories import CardRepository, SnapshotRepository
from orket.logging import log_event
from orket.orchestration.notes import NoteStore
from orket.runtime_paths import control_plane_db_for_runtime
from orket.schema import CardStatus, EnvironmentConfig, EpicConfig, IssueConfig, TeamConfig
from orket.time_utils import utc_now_iso

from . import orchestrator_ops
from .turn_approval_publication import create_pending_tool_approval_request


class Orchestrator:
    """Coordinates execution, verification, and ordered issue publication."""

    def __init__(
        self,
        workspace: Path,
        async_cards: CardRepository,
        snapshots: SnapshotRepository,
        org: Any,
        config_root: Path,
        db_path: str,
        loader: Any,
        sandbox_orchestrator: Any,
        card_completion: CardCompletionService | None = None,
        failure_report_clock: Callable[[], str] = utc_now_iso,
        control_plane_clock: Callable[[], str] | None = None,
        environment: Mapping[str, str] | None = None,
        *, architecture_policy: ArchitecturePolicySnapshot, turn_clock: Callable[[], datetime],
        user_settings: Mapping[str, Any] | None = None,
    ) -> None:
        if not isinstance(architecture_policy, ArchitecturePolicySnapshot):
            raise TypeError("E_ARCHITECTURE_POLICY_SNAPSHOT_REQUIRED")
        captured_settings = dict(user_settings) if user_settings is not None else None
        self.architecture_policy = architecture_policy
        self.decision_environment = MappingProxyType(dict(os.environ if environment is None else environment))
        self.workspace = workspace.resolve()
        self.async_cards = async_cards
        self.card_completion = card_completion
        self.failure_report_clock = failure_report_clock
        self.turn_clock = turn_clock
        self.snapshots = snapshots
        self.org = org
        self.config_root = config_root
        self.db_path = str(Path(db_path).resolve())
        self.loader = loader
        self.sandbox_orchestrator = sandbox_orchestrator

        from orket.services.memory_store import MemoryStore

        memory_db = Path(self.db_path).parent / "project_memory.db"
        self.memory = MemoryStore(memory_db)

        self.notes = NoteStore()
        self.transcript: list[Any] = []
        self._sandbox_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._sandbox_failed_rocks: set[str] = set()
        self.team_replan = TeamReplanScheduler()
        self.pending_gates = AsyncPendingGateRepository(self.db_path)
        control_plane_db_path = control_plane_db_for_runtime(runtime_db=self.db_path)
        self.control_plane_repository = AsyncControlPlaneRecordRepository(control_plane_db_path)
        self.control_plane_execution_repository = AsyncControlPlaneExecutionRepository(control_plane_db_path)
        self.control_plane_publication = ControlPlanePublicationService(repository=self.control_plane_repository)
        self.issue_control_plane = OrchestratorIssueControlPlaneService(
            execution_repository=self.control_plane_execution_repository,
            publication=self.control_plane_publication,
            transactions=SQLiteControlPlaneTransactions(control_plane_db_path),
            now_utc=control_plane_clock if control_plane_clock is not None else utc_now_iso,
        )
        self.scheduler_control_plane = OrchestratorSchedulerControlPlaneService(
            execution_repository=self.control_plane_execution_repository,
            publication=self.control_plane_publication,
            now_utc=control_plane_clock if control_plane_clock is not None else utc_now_iso,
        )
        self.tool_approval_control_plane_reservation = ToolApprovalControlPlaneReservationService(
            publication=self.control_plane_publication
        )
        self.decision_nodes = build_decision_node_registry(
            environment=self.decision_environment, user_settings=captured_settings)
        self.planner_node = self.decision_nodes.resolve_planner(self.org)
        self.router_node = self.decision_nodes.resolve_router(self.org)
        self.evaluator_node = self.decision_nodes.resolve_evaluator(self.org)
        self.loop_policy_node = self.decision_nodes.resolve_orchestration_loop(self.org)
        self.loop_inputs = capture_loop_policy_inputs(self.org, self.decision_environment)
        self.context_window = self.loop_policy_node.context_window(self.loop_inputs)
        self.model_clients = ModelClientFactory(self.decision_environment)
        self.support_services = OrchestratorSupportServices()

    async def _request_issue_transition(
        self: Any,
        *,
        issue: IssueConfig,
        target_status: CardStatus,
        reason: str,
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
        roles: list[str] | None = None,
        allow_policy_override: bool = True,
        completion_request: CardCompletionRequest | None = None,
    ) -> None:
        current_status = (
            issue.status if isinstance(issue.status, CardStatus) else CardStatus(str(issue.status).strip().lower())
        )
        wait_reason = resolve_transition_wait_reason(target_status=target_status, reason=reason, metadata=metadata)
        metadata_payload = dict(metadata or {})
        if wait_reason is not None and "wait_reason" not in metadata_payload:
            metadata_payload["wait_reason"] = wait_reason
        if current_status != target_status:
            validate_issue_transition(
                issue=issue,
                current_status=current_status,
                target_status=target_status,
                reason=reason,
                roles=roles,
                wait_reason=wait_reason,
                allow_policy_override=allow_policy_override,
                workflow_profile=orchestrator_policy.select_workflow_profile(
                    process_rules=orchestrator_policy.organization_process_rules(self.org)
                ),
            )
        await self.async_cards.update_status(
            issue.id,
            target_status,
            assignee=assignee,
            reason=reason,
            metadata=metadata_payload or None,
            **{"completion_request": completion_request} if target_status.value in SUCCESSFUL_CARD_STATUSES else {},
        )
        apply_issue_transition_locally(
            issue=issue, target_status=target_status, assignee=assignee, wait_reason=wait_reason
        )
        await self._publish_issue_control_plane_transition(
            issue=issue,
            current_status=current_status,
            target_status=target_status,
            reason=reason,
            assignee=assignee,
            metadata_payload=metadata_payload,
        )
        issue.status = target_status

    def _resolve_small_project_team_policy(self, epic: Any, team: Any) -> dict[str, Any]:
        issue_count = len(list(getattr(epic, "issues", []) or []))
        threshold = orchestrator_team_policy.small_project_issue_threshold(self.org)
        active = 0 < issue_count <= threshold
        variant = orchestrator_policy.select_small_project_builder_variant(
            user_settings=self.support_services.load_user_settings(),
            process_rules=orchestrator_policy.organization_process_rules(self.org),
        )
        return orchestrator_team_policy.project_team_policy(
            team, issue_count=issue_count, threshold=threshold, active=active, variant=variant,
        )

    def _history_context(self, *args: Any, **kwargs: Any) -> Any:
        return orchestrator_ops._history_context(self, *args, **kwargs)

    async def _execute_issue_turn(self, *args: Any, **kwargs: Any) -> Any:
        return await orchestrator_ops._execute_issue_turn(self, *args, **kwargs)

    def _validate_guard_rejection_payload(self, *args: Any, **kwargs: Any) -> Any:
        return orchestrator_ops._validate_guard_rejection_payload(self, *args, **kwargs)

    async def _create_pending_gate_request(self, *args: Any, **kwargs: Any) -> Any:
        return await orchestrator_ops._create_pending_gate_request(self, *args, **kwargs)

    async def _create_pending_tool_approval_request(self, *args: Any, **kwargs: Any) -> Any:
        return await create_pending_tool_approval_request(self, *args, **kwargs)

    async def _build_turn_context(self, *args: Any, **kwargs: Any) -> Any:
        return await orchestrator_ops._build_turn_context(self, *args, **kwargs)

    async def _build_dependency_context(self, *args: Any, **kwargs: Any) -> Any:
        return await orchestrator_ops._build_dependency_context(self, *args, **kwargs)

    def _extract_guard_review_payload(self, *args: Any, **kwargs: Any) -> Any:
        return orchestrator_ops._extract_guard_review_payload(self, *args, **kwargs)

    def _resolve_guard_event(self, *args: Any, **kwargs: Any) -> Any:
        return orchestrator_ops._resolve_guard_event(self, *args, **kwargs)

    async def _dispatch_turn(self, *args: Any, **kwargs: Any) -> Any:
        return await orchestrator_ops._dispatch_turn(self, *args, **kwargs)

    async def _handle_failure(self, *args: Any, **kwargs: Any) -> Any:
        return await orchestrator_ops._handle_failure(self, *args, **kwargs)

    def _is_issue_idesign_enabled(self, *args: Any, **kwargs: Any) -> Any:
        return orchestrator_ops._is_issue_idesign_enabled(self, *args, **kwargs)

    def _normalize_governance_violation_message(self, *args: Any, **kwargs: Any) -> Any:
        return orchestrator_ops._normalize_governance_violation_message(self, *args, **kwargs)

    async def verify_issue(self, issue_id: str, run_id: str | None = None) -> Any:
        """Runs empirical verification for a specific issue."""
        from orket.application.services.fixture_verification_service import FixtureVerificationService
        from orket.application.services.sandbox_verification_service import SandboxVerificationService
        from orket.core.domain.sandbox import SandboxStatus

        workspace, utc_now = (self.workspace, self.turn_clock)
        fixture_verifier = FixtureVerificationService(workspace, utc_now=utc_now, environment=self.decision_environment)
        sandbox_verifier = SandboxVerificationService(utc_now=utc_now)
        issue_data = await self.async_cards.get_by_id(issue_id)
        if not issue_data:
            from orket.exceptions import CardNotFound

            raise CardNotFound(f"Cannot verify non-existent issue {issue_id}")
        if hasattr(issue_data, "model_dump"):
            issue_payload = issue_data.model_dump()
        elif isinstance(issue_data, dict):
            issue_payload = dict(issue_data)
        else:
            issue_payload = dict(getattr(issue_data, "__dict__", {}))
        issue = IssueConfig.model_validate(issue_payload)
        verification_event = {"issue_id": issue_id}
        if run_id:
            verification_event["run_id"] = run_id
        log_event("verification_started", verification_event, workspace)
        result = await fixture_verifier.verify(issue.verification)
        rock_id = issue.build_id
        sandbox = self.sandbox_orchestrator.registry.get(f"sandbox-{rock_id}")
        if sandbox and sandbox.status == SandboxStatus.RUNNING:
            sandbox_event = {"issue_id": issue_id}
            if run_id:
                sandbox_event["run_id"] = run_id
            log_event("verification_sandbox_started", sandbox_event, workspace)
            sb_result = await sandbox_verifier.verify_sandbox(sandbox, issue.verification)
            result.passed += sb_result.passed
            result.failed += sb_result.failed
            result.total_scenarios += sb_result.total_scenarios
            result.logs.extend(sb_result.logs)
        issue.verification.last_run = result
        await self.async_cards.save(issue.model_dump())
        return result

    async def _trigger_sandbox(self, epic: EpicConfig, run_id: str | None = None) -> Any:
        return await orchestrator_ops._trigger_sandbox(self, epic, run_id)

    async def execute_epic(
        self,
        *,
        active_build: str,
        run_id: str,
        epic: EpicConfig,
        team: TeamConfig,
        env: EnvironmentConfig,
        target_issue_id: str | None = None,
        resume_mode: bool = False,
        model_override: str | None = None,
        approval_resume_turns: dict[str, int] | None = None,
    ) -> list[IssueConfig]:
        return cast(
            list[IssueConfig],
            await orchestrator_ops.execute_epic(
                self,
                active_build=active_build,
                run_id=run_id,
                epic=epic,
                team=team,
                env=env,
                target_issue_id=cast(Any, target_issue_id),
                resume_mode=resume_mode,
                model_override=model_override,
                approval_resume_turns=approval_resume_turns,
            ),
        )

    async def _save_checkpoint(
        self,
        run_id: str,
        epic: EpicConfig,
        team: TeamConfig,
        env: EnvironmentConfig,
        active_build: str,
    ) -> Any:
        return await orchestrator_ops._save_checkpoint(self, run_id, epic, team, env, active_build)

    async def _publish_issue_control_plane_transition(
        self: Any,
        *,
        issue: IssueConfig,
        current_status: CardStatus,
        target_status: CardStatus,
        reason: str,
        assignee: str | None,
        metadata_payload: dict[str, Any],
    ) -> None:
        session_id = str(metadata_payload.get("run_id") or "").strip()
        if not session_id:
            return
        handled_by_dispatch = False
        issue_control_plane = getattr(self, "issue_control_plane", None)
        if issue_control_plane is not None:
            handled_by_dispatch = await issue_control_plane.publish_issue_transition(
                session_id=session_id,
                issue_id=issue.id,
                current_status=current_status,
                target_status=target_status,
                reason=reason,
                assignee=assignee,
                turn_index=metadata_payload.get("turn_index"),
                review_turn=bool(metadata_payload.get("review_turn", False)),
            )
        scheduler_control_plane = getattr(self, "scheduler_control_plane", None)
        if (
            scheduler_control_plane is None
            or handled_by_dispatch
            or str(reason or "").strip().lower() == "turn_dispatch"
        ):
            return
        await scheduler_control_plane.publish_scheduler_transition(
            session_id=session_id,
            issue_id=issue.id,
            current_status=current_status,
            target_status=target_status,
            reason=reason,
            assignee=assignee,
            metadata=metadata_payload,
        )


__all__ = ["Orchestrator"]
