from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import BuiltInConnectorRegistry
from orket.application.services.outward_approval_service import (
    OutwardApprovalService,
)
from orket.application.services.outward_connector_service import (
    OutwardConnectorService,
)
from orket.application.services.outward_control_plane_service import begin_outward_execution, require_outward_authority
from orket.application.services.outward_effect_service import OutwardEffectService
from orket.application.services.outward_model_admission_inputs import admit_model_turn
from orket.application.services.outward_model_admission_service import OutwardModelAdmissionService
from orket.application.services.outward_model_publication import append_new_event
from orket.application.services.outward_model_tool_call_service import (
    OutwardModelToolCallService,
)
from orket.application.services.outward_run_execution_plan import (
    OutwardRunExecutionPlanError,
    acceptance_tool_steps,
)
from orket.application.services.outward_run_lifecycle import (
    turn_started_event,
)
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.application.services.trust_handoff_admission import TrustHandoffAdmissionService
from orket.core.domain.outward_effects import OutwardEffectRecoveryRequest
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord


class OutwardRunExecutionError(RuntimeError):
    pass


class OutwardRunExecutionValidationError(ValueError):
    pass


class OutwardRunExecutionService:
    def __init__(
        self,
        *,
        run_store: OutwardRunStore,
        event_store: OutwardRunEventStore,
        approval_service: OutwardApprovalService,
        connector_registry: BuiltInConnectorRegistry,
        workspace_root: Path,
        utc_now: Callable[[], str],
        connector_service: OutwardConnectorService | None = None,
        model_tool_call_service: OutwardModelToolCallService | None = None,
        http_allowlist: tuple[str, ...] = (),
        effect_owner_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.run_store = run_store
        self.event_store = event_store
        self.approval_service = approval_service
        self.connector_registry = connector_registry
        self.connector_service = connector_service or OutwardConnectorService(
            connector_registry=connector_registry,
            workspace_root=workspace_root,
            http_allowlist=http_allowlist,
        )
        self.model_tool_call_service = model_tool_call_service or OutwardModelToolCallService(
            connector_registry=connector_registry,
            workspace_root=workspace_root,
        )
        self.trust_handoff_admission = TrustHandoffAdmissionService(
            run_store=run_store,
            event_store=event_store,
            utc_now=utc_now,
            unit_of_work=approval_service.unit_of_work,
        )
        self.utc_now = utc_now
        self.effects = OutwardEffectService(
            unit_of_work=approval_service.unit_of_work, connectors=self.connector_service, utc_now=utc_now,
            owner_id_factory=effect_owner_id_factory or RuntimeInputService().create_effect_owner_id,
        )

        self.models = OutwardModelAdmissionService(
            approvals=approval_service, connectors=self.connector_service, model=self.model_tool_call_service,
            utc_now=utc_now, owner_id_factory=effect_owner_id_factory or RuntimeInputService().create_effect_owner_id,
        )

    async def start_if_ready(self, run_id: str) -> OutwardRunRecord:
        run = await self._require_run(run_id)
        run.require_execution_admission()
        if run.status == "queued":
            if _acceptance_steps(run) or run.task.get("acceptance_contract", {}).get("handoff_required"):
                async with self.approval_service.unit_of_work.transaction() as transaction:
                    await begin_outward_execution(transaction, run)
            run, admitted = await self.trust_handoff_admission.admit_if_required(run)
            if not admitted or not _acceptance_steps(run):
                return run
            async with self.approval_service.unit_of_work.transaction() as transaction:
                current = await transaction.get_run(run.run_id)
                if current != run:
                    if current is None or current.status == "queued":
                        raise OutwardRunExecutionError("E_OUTWARD_RUN_START_CONFLICT")
                else:
                    at = self.utc_now()
                    started = replace(run, status="running", started_at=run.started_at or at, current_turn=1)
                    await transaction.update_run(started)
                    await append_new_event(transaction, LedgerEvent(
                        event_id=f"run:{run.run_id}:0100:started", event_type="run_started", run_id=run.run_id,
                        turn=0, agent_id="outward-agent", at=at,
                        payload={"run_id": run.run_id, "status": "running", "started_at": started.started_at},
                    ))
                    await append_new_event(transaction, turn_started_event(started, at=at))
                    await admit_model_turn(transaction, started, at=at)
        return await self.models.execute(run.run_id)

    async def continue_after_approval(self, proposal_id: str) -> OutwardRunRecord:
        return await self._continue_effect_result(*await self.effects.execute(proposal_id))

    async def recover_effect(
        self, proposal_id: str, *, request_id: str, expected_owner_id: str,
        expected_fencing_generation: int, operator_ref: str,
    ) -> OutwardRunRecord:
        request = OutwardEffectRecoveryRequest(proposal_id, request_id, expected_owner_id, expected_fencing_generation, operator_ref)
        return await self._continue_effect_result(*await self.effects.recover(request))

    async def _continue_effect_result(self, run: OutwardRunRecord, advance: bool) -> OutwardRunRecord:
        if not advance:
            return run
        return await self.models.execute(run.run_id)

    async def continue_after_denial(self, proposal_id: str) -> OutwardRunRecord:
        proposal = await self.approval_service.get(proposal_id)
        if proposal is None:
            raise OutwardRunExecutionError(f"Approval proposal '{proposal_id}' not found")
        # Denial and terminal publication now commit in the approval transaction.
        return await self._require_run(proposal.run_id)

    async def _require_run(self, run_id: str) -> OutwardRunRecord:
        async with self.approval_service.unit_of_work.transaction() as transaction:
            run = await transaction.get_run(str(run_id or "").strip())
            if run is None:
                raise OutwardRunExecutionError(f"Run '{run_id}' not found")
            await require_outward_authority(transaction, run)
            return run


def _acceptance_steps(run: OutwardRunRecord) -> list[dict[str, Any]]:
    try:
        return acceptance_tool_steps(run)
    except OutwardRunExecutionPlanError as exc:
        raise OutwardRunExecutionValidationError(str(exc)) from exc

__all__ = [
    "OutwardRunExecutionError",
    "OutwardRunExecutionService",
    "OutwardRunExecutionValidationError",
]
