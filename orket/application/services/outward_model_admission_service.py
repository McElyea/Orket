from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from orket.application.services.outward_approval_service import OutwardApprovalService
from orket.application.services.outward_connector_service import (
    OutwardConnectorArgumentError,
    OutwardConnectorPolicyError,
    OutwardConnectorService,
)
from orket.application.services.outward_control_plane_service import require_outward_authority
from orket.application.services.outward_model_admission_inputs import validate_admission_inputs
from orket.application.services.outward_model_observability import verify_model_evidence
from orket.application.services.outward_model_publication import (
    MODEL_PROPOSAL_CONTEXT,
    policy_reject,
    record_model_proposal_event,
)
from orket.application.services.outward_model_recovery_records import validate_model_attempt_history
from orket.application.services.outward_model_recovery_service import OutwardModelRecoveryService
from orket.application.services.outward_model_tool_call_service import (
    OutwardModelToolCallError,
    OutwardModelToolCallService,
)
from orket.application.services.outward_run_execution_plan import (
    acceptance_tool_steps,
    current_step,
    current_step_index,
)
from orket.application.services.outward_terminal_service import publish_outward_terminal
from orket.core.domain.outward_authorization import canonical_json
from orket.core.domain.outward_model_admission import OutwardModelAdmission, admission_digest
from orket.core.domain.outward_runs import OutwardRunRecord


class OutwardModelAdmissionService:
    def __init__(
        self, *, approvals: OutwardApprovalService, connectors: OutwardConnectorService,
        model: OutwardModelToolCallService, utc_now: Callable[[], str], owner_id_factory: Callable[[], str],
    ) -> None:
        self.approvals, self.connectors, self.model = approvals, connectors, model
        self.unit_of_work = approvals.unit_of_work
        self.utc_now, self.owner_id_factory = utc_now, owner_id_factory
        self.recovery = OutwardModelRecoveryService(self.unit_of_work, utc_now)

    async def execute(self, run_id: str) -> OutwardRunRecord:
        run, admission, owned = await self._claim(run_id)
        if admission is None:
            return run
        if owned:
            result = await self._produce(run, admission)
            admission = await self._observe(admission, result)
        return await self._publish(admission)

    async def _claim(self, run_id: str) -> tuple[OutwardRunRecord, OutwardModelAdmission | None, bool]:
        async with self.unit_of_work.transaction() as transaction:
            run = await transaction.get_run(run_id)
            if run is None:
                raise RuntimeError("E_OUTWARD_MODEL_RUN_MISSING")
            await require_outward_authority(transaction, run)
            if run.status != "running":
                return run, None, False
            attempts = await transaction.models.list_attempts(run_id, run.execution_generation, run.current_turn, current_step_index(run))
            await validate_model_attempt_history(transaction, attempts)
            admission = attempts[-1] if attempts else None
            if admission is None:
                raise RuntimeError("E_OUTWARD_MODEL_ADMISSION_MISSING")
            validate_admission_inputs(admission, run)
            if admission.state == "observed":
                return run, admission, False
            if admission.state != "ready":
                raise RuntimeError("E_OUTWARD_MODEL_ADMISSION_UNRESOLVED")
            owned = replace(admission, state="claimed", owner_id=self.owner_id_factory(), claimed_at=self.utc_now())
            await transaction.models.transition(admission, owned)
            return run, owned, True

    async def _produce(self, run: OutwardRunRecord, admission: OutwardModelAdmission) -> dict[str, Any]:
        step = current_step(run, acceptance_tool_steps(run))
        if step is None:
            return {"error": "E_OUTWARD_NEXT_STEP_MISSING"}
        tool = step["tool"]
        if self.connectors.connector_registry.get(tool) is None:
            return {"error": f"acceptance_contract tool is not registered: {tool}"}
        if tool not in set(run.policy_overrides.get("approval_required_tools") or []):
            return {"error": f"acceptance_contract tool is not approval-required: {tool}"}
        try:
            result = await self.model.produce_governed_tool_call(
                run=run, expected_tool=tool, governed_tools={tool}, evidence_scope=admission.evidence_scope,
            )
        except OutwardModelToolCallError as exc:
            return {"error": str(exc)}
        return {"tool_call": result.tool_call, "model_invocation": result.model_invocation}

    async def _observe(self, admission: OutwardModelAdmission, result: dict[str, Any]) -> OutwardModelAdmission:
        payload = canonical_json(result)
        observed = replace(admission, state="observed", result_json=payload,
                           result_digest=admission_digest(payload), observed_at=self.utc_now())
        async with self.unit_of_work.transaction() as transaction:
            run = await transaction.get_run(admission.run_id)
            if run is None:
                raise RuntimeError("E_OUTWARD_MODEL_RUN_MISSING")
            await require_outward_authority(transaction, run)
            attempts = await transaction.models.list_attempts(admission.run_id, admission.execution_generation, admission.turn, admission.step_index)
            await validate_model_attempt_history(transaction, attempts)
            if not attempts or attempts[-1] != admission:
                raise RuntimeError("E_OUTWARD_MODEL_ADMISSION_FENCE_CONFLICT")
            validate_admission_inputs(admission, run)
            await transaction.models.transition(admission, observed)
        return observed

    async def _publish(self, expected: OutwardModelAdmission) -> OutwardRunRecord:
        async with self.unit_of_work.transaction() as transaction:
            attempts = await transaction.models.list_attempts(expected.run_id, expected.execution_generation, expected.turn, expected.step_index)
            await validate_model_attempt_history(transaction, attempts)
            admission = attempts[-1] if attempts else None
            run = await transaction.get_run(expected.run_id)
            if admission is None or run is None:
                raise RuntimeError("E_OUTWARD_MODEL_ADMISSION_MISSING")
            await require_outward_authority(transaction, run)
            if admission.state == "published" and replace(admission, state="observed", published_at=None) == expected:
                return run
            if admission != expected or admission.state != "observed":
                raise RuntimeError("E_OUTWARD_MODEL_ADMISSION_CONFLICT")
            validate_admission_inputs(admission, run)
            at = self.utc_now()
            projected = await self._project(transaction, run, admission, at=at)
            await transaction.models.transition(admission, replace(admission, state="published", published_at=at))
            return projected

    async def _project(self, transaction, run: OutwardRunRecord, admission: OutwardModelAdmission, *, at: str) -> OutwardRunRecord:
        result = admission.result
        reason = self._invalid_result(run, result)
        if reason:
            return await publish_outward_terminal(transaction, run, at=at, reason=reason, outcome="failed", cause=admission)
        tool_call, evidence = result["tool_call"], result["model_invocation"]
        tool = tool_call["tool"]
        connector = self.connectors.connector_registry.get(tool)
        await verify_model_evidence(workspace_root=self.model.workspace_root, evidence=evidence)
        projected = await record_model_proposal_event(transaction, run, tool, tool_call, evidence, connector.pii_fields, at=at)
        try:
            await asyncio.to_thread(self.connectors.validate_policy, tool, tool_call["args"])
        except OutwardConnectorPolicyError as exc:
            return await policy_reject(transaction, projected, tool, tool_call, connector.pii_fields, exc.reason, at=at)
        timeout = int(run.policy_overrides.get("approval_timeout_seconds") or connector.timeout_seconds)
        await self.approvals.request_in_transaction(
            transaction, run_id=run.run_id, tool=tool, args=tool_call["args"],
            context_summary=MODEL_PROPOSAL_CONTEXT,
            timeout_seconds=timeout,
        )
        return await transaction.get_run(run.run_id)

    def _invalid_result(self, run: OutwardRunRecord, result: dict[str, Any]) -> str | None:
        if "error" in result:
            return result["error"]
        call = result["tool_call"]
        tool = call["tool"]
        if self.connectors.connector_registry.get(tool) is None:
            return f"model tool is not registered: {tool}"
        if tool != current_step(run, acceptance_tool_steps(run))["tool"]:
            return f"model tool does not match acceptance_contract tool: {tool}"
        try:
            self.connectors.validate_args(tool, call["args"])
        except OutwardConnectorArgumentError as exc:
            return f"invalid model connector args for {tool}: {exc.errors}"
        return None
