import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_repositories import (
    AsyncPendingGateRepository,
    AsyncSessionRepository,
    AsyncSnapshotRepository,
    AsyncSuccessRepository,
)
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_operator_service import (
    KernelActionControlPlaneOperatorService,
)
from orket.application.services.kernel_action_control_plane_resource_lifecycle import reservation_id_for_run
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.application.services.kernel_action_control_plane_view_service import KernelActionControlPlaneViewService
from orket.application.services.kernel_action_pending_approval_reservation import (
    publish_pending_kernel_approval_hold_if_needed,
)
from orket.application.services.kernel_v1_gateway import KernelV1Gateway
from orket.application.services.tool_approval_control_plane_operator_service import (
    ToolApprovalControlPlaneOperatorService,
)
from orket.core.domain import OperatorCommandClass, OperatorInputClass
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.logging import log_event
from orket.orchestration import engine_approvals
from orket.orchestration.engine_services import CardArchiver, KernelGatewayFacade, SandboxManager, SessionController
from orket.runtime.config_loader import ConfigLoader
from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.runtime.run_ledger_factory import build_run_ledger_repository
from orket.runtime.runtime_context import OrketRuntimeContext
from orket.runtime_paths import resolve_control_plane_db_path


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
    ):
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.engine_runtime_node = self.decision_nodes.resolve_engine_runtime()
        self.engine_runtime_node.bootstrap_environment()
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
            config_root_resolver=self.engine_runtime_node.resolve_config_root,
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
        self.pending_gates = AsyncPendingGateRepository(self.db_path)
        self.control_plane_repository = AsyncControlPlaneRecordRepository(resolve_control_plane_db_path())
        self.control_plane_execution_repository = AsyncControlPlaneExecutionRepository(resolve_control_plane_db_path())
        self.control_plane_publication = ControlPlanePublicationService(repository=self.control_plane_repository)
        self.tool_approval_control_plane_operator = ToolApprovalControlPlaneOperatorService(
            publication=self.control_plane_publication
        )
        self.kernel_action_control_plane = KernelActionControlPlaneService(
            execution_repository=self.control_plane_execution_repository,
            publication=self.control_plane_publication,
        )
        self.kernel_action_control_plane_operator = KernelActionControlPlaneOperatorService(
            publication=self.control_plane_publication
        )
        self.kernel_action_control_plane_view = KernelActionControlPlaneViewService(
            record_repository=self.control_plane_repository,
            execution_repository=self.control_plane_execution_repository,
        )
        self.kernel_gateway = kernel_gateway or KernelV1Gateway()

        self._pipeline = ExecutionPipeline(
            self.workspace_root,
            self.department,
            runtime_context=self.runtime_context,
        )
        self.sandbox_manager = SandboxManager(getattr(self._pipeline, "sandbox_orchestrator", None))
        self.session_controller = SessionController(self.workspace_root)
        self.card_archiver = CardArchiver(self.cards)
        self.kernel_gateway_facade = KernelGatewayFacade(self.kernel_gateway)

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
        build_id: str = None,
        session_id: str = None,
        driver_steered: bool = False,
        target_issue_id: str = None,
        model_override: str | None = None,
    ) -> dict[str, Any]:
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
        build_id: str = None,
        session_id: str = None,
        driver_steered: bool = False,
        target_issue_id: str = None,
        model_override: str | None = None,
    ) -> list[dict]:
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
        build_id: str = None,
        session_id: str = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        """Compatibility wrapper over the canonical run_card surface."""
        return await self.run_card(
            issue_id,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            model_override=model_override,
        )

    async def run_rock(
        self,
        rock_name: str,
        build_id: str = None,
        session_id: str = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> dict[str, Any]:
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

    async def stop_sandbox(self, sandbox_id: str, *, operator_actor_ref: str | None = None):
        """Stops and deletes a sandbox."""
        await self.sandbox_manager.stop(sandbox_id, operator_actor_ref=operator_actor_ref)

    async def halt_session(self, session_id: str, *, operator_actor_ref: str | None = None):
        """Halts an active session by signaling the runtime state."""
        cancelled_active_task = await self.session_controller.halt(session_id)
        if operator_actor_ref:
            timestamp = datetime.now(UTC).isoformat()
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

    def replay_turn(
        self, session_id: str, issue_id: str, turn_index: int, role: str | None = None
    ) -> dict[str, Any]:
        """
        Replay diagnostics for one turn from persisted observability artifacts.
        """
        run_root = self.workspace_root / "observability" / session_id / issue_id
        if not run_root.exists():
            raise FileNotFoundError(f"No observability artifacts found for run={session_id} issue={issue_id}")

        prefix = f"{turn_index:03d}_"
        candidates = [p for p in run_root.iterdir() if p.is_dir() and p.name.startswith(prefix)]
        if role:
            role_suffix = role.lower().replace(" ", "_")
            candidates = [p for p in candidates if p.name.endswith(role_suffix)]
        if not candidates:
            raise FileNotFoundError(f"No turn artifacts found for turn_index={turn_index}")

        target = sorted(candidates)[0]
        checkpoint_path = target / "checkpoint.json"
        messages_path = target / "messages.json"
        model_path = target / "model_response.txt"
        parsed_tools_path = target / "parsed_tool_calls.json"

        def _read_json(path: Path) -> Any:
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))

        return {
            "turn_dir": str(target),
            "checkpoint": _read_json(checkpoint_path),
            "messages": _read_json(messages_path),
            "model_response": model_path.read_text(encoding="utf-8") if model_path.exists() else None,
            "parsed_tool_calls": _read_json(parsed_tools_path),
        }

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
        response = self.kernel_gateway_facade.admit_proposal(request)
        ledger = self.kernel_gateway_facade.list_ledger_events(
            {
                "contract_version": "kernel_api/v1",
                "session_id": request.get("session_id"),
                "trace_id": request.get("trace_id"),
                "limit": 200,
            }
        )
        run, _attempt = await self.kernel_action_control_plane.record_admission(
            request=request,
            response=response,
            ledger_items=list(ledger.get("items") or []),
        )
        await publish_pending_kernel_approval_hold_if_needed(
            engine=self,
            session_id=str(request.get("session_id") or ""),
            trace_id=str(request.get("trace_id") or ""),
            proposal=dict(request.get("proposal") or {}),
            response=response,
        )
        view_service = getattr(self, "kernel_action_control_plane_view", None)
        if view_service is not None:
            return await view_service.augment_kernel_response(
                response=response,
                session_id=str(request.get("session_id") or ""),
                trace_id=str(request.get("trace_id") or ""),
            )
        reservation = await self.control_plane_repository.get_latest_reservation_record(
            reservation_id=reservation_id_for_run(run_id=run.run_id)
        )
        if reservation is not None:
            return {
                **response,
                "control_plane_run_id": run.run_id,
                "control_plane_reservation_id": reservation.reservation_id,
            }
        return response

    def kernel_commit_proposal(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.commit_proposal(request)

    async def kernel_commit_proposal_async(self, request: dict[str, Any]) -> dict[str, Any]:
        response = self.kernel_gateway_facade.commit_proposal(request)
        ledger = self.kernel_gateway_facade.list_ledger_events(
            {
                "contract_version": "kernel_api/v1",
                "session_id": request.get("session_id"),
                "trace_id": request.get("trace_id"),
                "limit": 400,
            }
        )
        await self.kernel_action_control_plane.record_commit(
            request=request,
            response=response,
            ledger_items=list(ledger.get("items") or []),
        )
        view_service = getattr(self, "kernel_action_control_plane_view", None)
        if view_service is None:
            return response
        return await view_service.augment_kernel_response(
            response=response,
            session_id=str(request.get("session_id") or ""),
            trace_id=str(request.get("trace_id") or ""),
        )

    def kernel_end_session(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.kernel_gateway_facade.end_session(request)

    async def kernel_end_session_async(self, request: dict[str, Any]) -> dict[str, Any]:
        response = self.kernel_gateway_facade.end_session(request)
        ledger = self.kernel_gateway_facade.list_ledger_events(
            {
                "contract_version": "kernel_api/v1",
                "session_id": request.get("session_id"),
                "trace_id": request.get("trace_id"),
                "limit": 200,
            }
        )
        closed = await self.kernel_action_control_plane.record_session_end(
            request=request,
            response=response,
            ledger_items=list(ledger.get("items") or []),
        )
        operator_actor_ref = str(request.get("operator_actor_ref") or "").strip()
        attestation_scope = str(request.get("attestation_scope") or "").strip()
        attestation_payload_raw = request.get("attestation_payload")
        attestation_payload = (
            dict(attestation_payload_raw)
            if isinstance(attestation_payload_raw, dict)
            else {}
        )
        if attestation_scope and not operator_actor_ref:
            raise ValueError(
                "kernel end-session attestation requires authenticated operator actor reference"
            )
        if closed is not None and operator_actor_ref:
            run, _attempt, _final_truth = closed
            session_end_timestamp = next(
                (
                    str(item.get("created_at") or "").strip()
                    for item in reversed(list(ledger.get("items") or []))
                    if str(item.get("event_type") or "") == "session.ended"
                ),
                "",
            )
            await self.kernel_action_control_plane_operator.publish_cancel_run_command(
                actor_ref=operator_actor_ref,
                session_id=str(request.get("session_id") or ""),
                trace_id=str(request.get("trace_id") or ""),
                timestamp=session_end_timestamp or str(run.creation_timestamp),
                receipt_ref=f"kernel-ledger-event:{response.get('event_digest')}",
                reason=str(request.get("reason") or "").strip() or None,
            )
            if attestation_scope:
                await self.kernel_action_control_plane_operator.publish_run_attestation(
                    actor_ref=operator_actor_ref,
                    session_id=str(request.get("session_id") or ""),
                    trace_id=str(request.get("trace_id") or ""),
                    timestamp=session_end_timestamp or str(run.creation_timestamp),
                    receipt_ref=f"kernel-ledger-event:{response.get('event_digest')}",
                    request_id=str(request.get("request_id") or "").strip() or None,
                    precondition_basis_ref=f"kernel-session-end:{str(request.get('reason') or '').strip() or 'unspecified'}",
                    attestation_scope=attestation_scope,
                    attestation_payload=attestation_payload,
                )
        view_service = getattr(self, "kernel_action_control_plane_view", None)
        if view_service is None:
            return response
        return await view_service.augment_kernel_response(
            response=response,
            session_id=str(request.get("session_id") or ""),
            trace_id=str(request.get("trace_id") or ""),
        )

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
