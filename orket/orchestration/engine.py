import asyncio
import inspect
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.async_repositories import (
    AsyncSessionRepository,
    AsyncSnapshotRepository,
    AsyncSuccessRepository,
)
from orket.application.services.kernel_v1_gateway import KernelV1Gateway
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.domain import OperatorCommandClass, OperatorInputClass
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.logging import log_event
from orket.orchestration import engine_approvals
from orket.orchestration.engine_kernel_async_service import KernelAsyncControlPlaneService
from orket.orchestration.engine_services import (
    CardArchiver,
    KernelGatewayFacade,
    ReplayDiagnosticsService,
    SandboxManager,
    SessionController,
    build_engine_control_plane_services,
)
from orket.runtime.config.runtime_bootstrap import DEFAULT_RUNTIME_BOOTSTRAP_SERVICE
from orket.runtime.config_loader import ConfigLoader
from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.runtime.run_ledger_factory import build_run_ledger_repository
from orket.runtime.runtime_context import OrketRuntimeContext


class OrchestrationEngine:
    """The Single Source of Truth for executing Orket Units."""

    def __init__(
        self,
        workspace_root: Path,
        department: str = "core",
        db_path: str | None = None,
        config_root: Path | None = None,
        cards_repo: AsyncCardRepository | None = None,
        sessions_repo: AsyncSessionRepository | None = None,
        snapshots_repo: AsyncSnapshotRepository | None = None,
        success_repo: AsyncSuccessRepository | None = None,
        run_ledger_repo: Any | None = None,
        decision_nodes: DecisionNodeRegistry | None = None,
        kernel_gateway: KernelV1Gateway | None = None,
        runtime_bootstrap_service: Any | None = None,
        runtime_inputs: RuntimeInputService | None = None,
    ) -> None:
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.runtime_bootstrap_service = runtime_bootstrap_service or DEFAULT_RUNTIME_BOOTSTRAP_SERVICE
        self.runtime_inputs = runtime_inputs or RuntimeInputService()
        self.runtime_bootstrap_service.bootstrap_environment()
        self.runtime_context = OrketRuntimeContext.from_env(
            workspace_root=workspace_root,
            department=department,
            db_path=db_path,
            config_root=config_root,
            cards_repo=cards_repo,
            sessions_repo=sessions_repo,
            snapshots_repo=snapshots_repo,
            success_repo=success_repo,
            run_ledger_repo=run_ledger_repo,
            decision_nodes=self.decision_nodes,
            config_loader_factory=ConfigLoader,
            config_loader_kwargs={"decision_nodes": self.decision_nodes},
            config_root_resolver=self.runtime_bootstrap_service.resolve_config_root,
            run_ledger_factory=build_run_ledger_repository,
            telemetry_sink=self._emit_run_ledger_telemetry,
        )
        self.workspace_root = self.runtime_context.workspace_root
        self.department = self.runtime_context.department
        self.db_path = self.runtime_context.db_path
        self.config_root = self.runtime_context.config_root
        self.loader = self.runtime_context.loader
        self.org = self.runtime_context.org
        self.orchestration_config = self.runtime_context.orchestration_config
        self.state_backend_mode = self.runtime_context.state_backend_mode
        self.run_ledger_mode = self.runtime_context.run_ledger_mode
        self.gitea_state_pilot_enabled = self.runtime_context.gitea_state_pilot_enabled
        self.cards = self.runtime_context.cards_repo
        self.sessions = self.runtime_context.sessions_repo
        self.snapshots = self.runtime_context.snapshots_repo
        self.success = self.runtime_context.success_repo
        self.run_ledger = self.runtime_context.run_ledger
        control_plane_services = build_engine_control_plane_services(db_path=self.db_path)
        self.pending_gates = control_plane_services.pending_gates
        self.control_plane_repository = control_plane_services.control_plane_repository
        self.control_plane_execution_repository = control_plane_services.control_plane_execution_repository
        self.control_plane_publication = control_plane_services.control_plane_publication
        self.tool_approval_control_plane_operator = control_plane_services.tool_approval_control_plane_operator
        self.kernel_action_control_plane = control_plane_services.kernel_action_control_plane
        self.kernel_action_control_plane_operator = control_plane_services.kernel_action_control_plane_operator
        self.kernel_action_control_plane_view = control_plane_services.kernel_action_control_plane_view
        self.kernel_gateway = kernel_gateway or KernelV1Gateway()

        self._pipeline = ExecutionPipeline(
            self.workspace_root,
            self.department,
            runtime_context=self.runtime_context,
            runtime_inputs=self.runtime_inputs,
        )
        self.sandbox_manager = SandboxManager(getattr(self._pipeline, "sandbox_orchestrator", None))
        self.session_controller = SessionController(self.workspace_root)
        self.card_archiver = CardArchiver(self.cards)
        self.kernel_gateway_facade = KernelGatewayFacade(self.kernel_gateway)
        self.replay_diagnostics = ReplayDiagnosticsService(self.workspace_root)
        self.kernel_async_control_plane = self._build_kernel_async_control_plane()
        self._initialize_lock = asyncio.Lock()
        self._initialized = False
        self._closed = False

    def _build_kernel_async_control_plane(self) -> KernelAsyncControlPlaneService:
        return KernelAsyncControlPlaneService(
            gateway_facade=self.kernel_gateway_facade,
            kernel_action_control_plane=self.kernel_action_control_plane,
            kernel_action_control_plane_operator=self.kernel_action_control_plane_operator,
            kernel_action_control_plane_view=self.kernel_action_control_plane_view,
            control_plane_repository=self.control_plane_repository,
            control_plane_publication=self.control_plane_publication,
            get_approval=lambda approval_id: self.get_approval(approval_id),
        )

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            await self.runtime_context.initialize()
            await self._pipeline.initialize()
            self._initialized = True

    async def close(self) -> None:
        if self._closed:
            return
        for target in (self._pipeline, self.runtime_context):
            close = getattr(target, "aclose", None) or getattr(target, "close", None)
            if not callable(close):
                continue
            maybe_awaitable = close()
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        self._closed = True

    async def _emit_run_ledger_telemetry(self, payload: dict[str, Any]) -> None:
        log_event(
            "run_ledger_telemetry",
            {
                "run_ledger_mode": self.run_ledger_mode,
                **dict(payload or {}),
            },
            workspace=self.workspace_root,
        )

    async def run_card(
        self,
        card_id: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        target_issue_id: str | None = None,
        model_override: str | None = None,
    ) -> Any:
        """Canonical public runtime entrypoint for epic, rock, and issue execution."""
        return await self._pipeline.run_card(
            card_id,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            target_issue_id=target_issue_id,
            model_override=model_override,
        )

    async def run_epic(
        self,
        epic_id: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        target_issue_id: str | None = None,
        model_override: str | None = None,
    ) -> Any:
        """Compatibility wrapper over the canonical run_card surface."""
        return await self.run_card(
            epic_id,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            target_issue_id=target_issue_id,
            model_override=model_override,
        )

    async def run_issue(
        self,
        issue_id: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> Any:
        """Compatibility wrapper over the canonical run_card surface."""
        return await self.run_card(
            issue_id,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            model_override=model_override,
        )

    async def resolve_run_card_target(self, card_id: str) -> tuple[str, str | None]:
        """Expose canonical runtime-target resolution for preflight callers."""
        await self.initialize()
        return await self._pipeline._resolve_run_card_target(card_id)

    async def run_rock(
        self,
        rock_name: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> Any:
        """Legacy compatibility wrapper over the canonical run_card surface."""
        return await self.run_card(
            rock_name,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            model_override=model_override,
        )

    async def run_gitea_state_loop(
        self,
        *,
        worker_id: str,
        fetch_limit: int = 5,
        lease_seconds: int = 30,
        renew_interval_seconds: float = 5.0,
        max_iterations: int | None = None,
        max_idle_streak: int | None = None,
        max_duration_seconds: float | None = None,
        idle_sleep_seconds: float = 0.0,
        summary_out: str | Path | None = None,
    ) -> dict[str, Any]:
        return await self._pipeline.run_gitea_state_loop(
            worker_id=worker_id,
            fetch_limit=fetch_limit,
            lease_seconds=lease_seconds,
            renew_interval_seconds=renew_interval_seconds,
            max_iterations=max_iterations,
            max_idle_streak=max_idle_streak,
            max_duration_seconds=max_duration_seconds,
            idle_sleep_seconds=idle_sleep_seconds,
            summary_out=summary_out,
        )

    def get_board(self) -> dict[str, Any]:
        from orket.board import get_board_hierarchy

        return get_board_hierarchy(self.department)

    async def get_sandboxes(self) -> list[dict[str, Any]]:
        """Returns list of active sandboxes."""
        return await self.sandbox_manager.list_active()

    async def stop_sandbox(self, sandbox_id: str, *, operator_actor_ref: str | None = None) -> None:
        """Stops and deletes a sandbox."""
        await self.sandbox_manager.stop(sandbox_id, operator_actor_ref=operator_actor_ref)

    async def halt_session(self, session_id: str, *, operator_actor_ref: str | None = None) -> None:
        """Halts an active session by signaling the runtime state."""
        cancelled_active_task = await self.session_controller.halt(session_id)
        if operator_actor_ref:
            timestamp = self.runtime_inputs.utc_now_iso()
            target_ref = f"session:{session_id}"
            await self.control_plane_publication.publish_operator_action(
                action_id=f"session-operator-action:{session_id}:halt:{timestamp}",
                actor_ref=operator_actor_ref,
                input_class=OperatorInputClass.COMMAND,
                target_ref=target_ref,
                timestamp=timestamp,
                precondition_basis_ref=f"{target_ref}:halt",
                result="accepted_cancel" if cancelled_active_task else "accepted_no_active_runtime_task",
                command_class=OperatorCommandClass.CANCEL_RUN,
                affected_transition_refs=[f"{target_ref}:runtime_task:{'cancelled' if cancelled_active_task else 'none'}"],
                affected_resource_refs=[target_ref],
                receipt_refs=[f"runtime-task:{session_id}"],
            )

    async def list_approvals(
        self,
        *,
        session_id: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await engine_approvals.list_approvals(
            self,
            session_id=session_id,
            status=status,
            request_id=request_id,
            limit=limit,
        )

    async def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        return await engine_approvals.get_approval(self, approval_id)

    async def decide_approval(
        self,
        *,
        approval_id: str,
        decision: str,
        edited_proposal: dict[str, Any] | None = None,
        notes: str | None = None,
        operator_actor_ref: str | None = None,
    ) -> dict[str, Any]:
        return await engine_approvals.decide_approval(
            self,
            approval_id=approval_id,
            decision=decision,
            edited_proposal=edited_proposal,
            notes=notes,
            operator_actor_ref=operator_actor_ref,
        )

    async def archive_card(self, card_id: str, archived_by: str = "system", reason: str | None = None) -> bool:
        """Archive a single card record in persistence."""
        return await self.card_archiver.archive_card(card_id, archived_by=archived_by, reason=reason)

    async def archive_cards(
        self,
        card_ids: list[str],
        archived_by: str = "system",
        reason: str | None = None,
    ) -> dict[str, list[str]]:
        """Archive multiple cards by id."""
        return await self.card_archiver.archive_cards(card_ids, archived_by=archived_by, reason=reason)

    async def archive_build(self, build_id: str, archived_by: str = "system", reason: str | None = None) -> int:
        """Archive all cards under a build id."""
        return await self.card_archiver.archive_build(build_id, archived_by=archived_by, reason=reason)

    async def archive_related_cards(
        self,
        related_tokens: list[str],
        archived_by: str = "system",
        reason: str | None = None,
        limit: int = 500,
    ) -> dict[str, list[str]]:
        """Archive cards whose id/build/summary/note matches any token."""
        return await self.card_archiver.archive_related_cards(
            related_tokens,
            archived_by=archived_by,
            reason=reason,
            limit=limit,
        )

    def replay_turn_diagnostics(
        self, session_id: str, issue_id: str, turn_index: int, role: str | None = None
    ) -> dict[str, Any]:
        """Artifact-backed diagnostics only. This is not the canonical replay-verdict authority path."""
        return self.replay_diagnostics.replay_turn_diagnostics(
            session_id=session_id,
            issue_id=issue_id,
            turn_index=turn_index,
            role=role,
        )

    def replay_turn(
        self, session_id: str, issue_id: str, turn_index: int, role: str | None = None
    ) -> dict[str, Any]:
        """Compatibility wrapper over replay diagnostics only; do not treat this as canonical replay truth."""
        return self.replay_turn_diagnostics(
            session_id=session_id,
            issue_id=issue_id,
            turn_index=turn_index,
            role=role,
        )

    def kernel_start_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.start_run(request)

    def kernel_execute_turn(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.execute_turn(request)

    def kernel_finish_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.finish_run(request)

    def kernel_resolve_capability(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.resolve_capability(request)

    def kernel_authorize_tool_call(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.authorize_tool_call(request)

    def kernel_replay_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.replay_run(request)

    def kernel_compare_runs(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.compare_runs(request)

    def kernel_projection_pack(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.projection_pack(request)

    def kernel_admit_proposal(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.admit_proposal(request)

    async def kernel_admit_proposal_async(self, request: dict[str, Any]) -> dict[str, Any]:
        self.kernel_async_control_plane = self._build_kernel_async_control_plane()
        return await self.kernel_async_control_plane.admit_proposal_async(request)

    def kernel_commit_proposal(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.commit_proposal(request)

    async def kernel_commit_proposal_async(self, request: dict[str, Any]) -> dict[str, Any]:
        self.kernel_async_control_plane = self._build_kernel_async_control_plane()
        return await self.kernel_async_control_plane.commit_proposal_async(request)

    def kernel_end_session(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.end_session(request)

    async def kernel_end_session_async(self, request: dict[str, Any]) -> dict[str, Any]:
        self.kernel_async_control_plane = self._build_kernel_async_control_plane()
        return await self.kernel_async_control_plane.end_session_async(request)

    def kernel_list_ledger_events(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.list_ledger_events(request)

    def kernel_rebuild_pending_approvals(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.rebuild_pending_approvals(request)

    def kernel_replay_action_lifecycle(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.replay_action_lifecycle(request)

    def kernel_audit_action_lifecycle(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.audit_action_lifecycle(request)

    def kernel_run_lifecycle(
        self,
        *,
        workflow_id: str,
        execute_turn_requests: list[dict[str, Any]],
        finish_outcome: str = "PASS",
        start_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.kernel_gateway_facade.run_lifecycle(
            workflow_id=workflow_id,
            execute_turn_requests=execute_turn_requests,
            finish_outcome=finish_outcome,
            start_request=start_request,
        )
