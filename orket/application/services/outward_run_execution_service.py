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
    redacted_args_preview,
)
from orket.application.services.outward_connector_service import (
    OutwardConnectorArgumentError,
    OutwardConnectorNotFoundError,
    OutwardConnectorPolicyError,
    OutwardConnectorService,
)
from orket.application.services.outward_model_tool_call_service import (
    OutwardModelToolCallError,
    OutwardModelToolCallService,
)
from orket.application.services.outward_run_execution_plan import (
    OutwardRunExecutionPlanError,
    acceptance_tool_steps,
    args_hash,
    current_step,
    failed_tool_event_payload,
    failure_reason,
    invalid_args_event_payload,
    is_last_step,
    model_tool_call,
    proposal_suffix,
    step_event_id,
    task_with_model_tool_call,
    task_with_tool_result,
)
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
        self.utc_now = utc_now

    async def start_if_ready(self, run_id: str) -> OutwardRunRecord:
        run = await self._require_run(run_id)
        steps = _acceptance_steps(run)
        if not steps or run.status != "queued":
            return run

        started = replace(run, status="running", started_at=run.started_at or self.utc_now(), current_turn=1)
        await self.run_store.update(started)
        await self._append_once(
            event_id=f"run:{run.run_id}:0100:started",
            event_type="run_started",
            run=started,
            turn=0,
            payload={"run_id": run.run_id, "status": "running", "started_at": started.started_at},
        )
        await self._start_turn(started, 1)
        return await self._handle_model_tool_call(started, steps[0])

    async def continue_after_approval(self, proposal_id: str) -> OutwardRunRecord:
        proposal = await self.approval_service.get(proposal_id)
        if proposal is None:
            raise OutwardRunExecutionError(f"Approval proposal '{proposal_id}' not found")
        run = await self._require_run(proposal.run_id)
        if run.status in {"completed", "failed"}:
            return run
        if proposal.status != "approved":
            return run

        tool_call = model_tool_call(run)
        if tool_call is None:
            return await self._fail_run(run, "approved proposal has no recorded model governed tool call")
        if tool_call["tool"] != proposal.tool:
            return await self._fail_run(run, f"approved proposal tool drifted from model tool: {proposal.tool}")

        try:
            tool_event_payload, tool_result = await self.connector_service.invoke_with_result(proposal.tool, tool_call["args"])
        except OutwardConnectorArgumentError as exc:
            tool_result = {"ok": False, "error": "invalid_args", "errors": exc.errors}
            tool_event_payload = invalid_args_event_payload(proposal.tool, tool_call["args"], exc.errors)
        except OutwardConnectorNotFoundError as exc:
            tool_result = {"ok": False, "error": str(exc)}
            tool_event_payload = failed_tool_event_payload(proposal.tool, tool_call["args"], str(exc))
        outcome = str(tool_event_payload.get("outcome") or "failed")
        await self._append_once(
            event_id=step_event_id(run.run_id, run.current_turn, 400, f"tool:{proposal.tool}:{proposal_suffix(proposal_id)}"),
            event_type="tool_invoked",
            run=run,
            turn=run.current_turn,
            payload=tool_event_payload,
        )
        if outcome != "success":
            return await self._fail_run(run, failure_reason(tool_event_payload))

        steps = _acceptance_steps(run)
        run_with_result = replace(
            run,
            task=task_with_tool_result(run, proposal_id=proposal_id, tool=proposal.tool, result=tool_result),
        )
        await self.run_store.update(run_with_result)
        if is_last_step(run, steps):
            return await self._complete_run(run_with_result, proposal.tool, proposal_id)
        return await self._advance_to_next_turn(run_with_result, proposal.tool, proposal_id, steps)

    async def continue_after_denial(self, proposal_id: str) -> OutwardRunRecord:
        proposal = await self.approval_service.get(proposal_id)
        if proposal is None:
            raise OutwardRunExecutionError(f"Approval proposal '{proposal_id}' not found")
        run = await self._require_run(proposal.run_id)
        if proposal.status != "denied":
            return run
        if run.status == "completed":
            return run
        await self._complete_turn(run, proposal.tool, proposal_id, outcome="denied")
        return await self._complete_terminal(
            run,
            status="completed",
            stop_reason=proposal.reason,
            outcome="denied",
            completed_at=proposal.decided_at or self.utc_now(),
        )

    async def _handle_model_tool_call(self, run: OutwardRunRecord, acceptance_tool_call: dict[str, Any]) -> OutwardRunRecord:
        acceptance_tool = acceptance_tool_call["tool"]
        connector = self.connector_registry.get(acceptance_tool)
        if connector is None:
            return await self._fail_run(run, f"acceptance_contract tool is not registered: {acceptance_tool}")
        required_tools = {str(tool).strip() for tool in (run.policy_overrides.get("approval_required_tools") or [])}
        if acceptance_tool not in required_tools:
            return await self._fail_run(run, f"acceptance_contract tool is not approval-required: {acceptance_tool}")
        try:
            model_result = await self.model_tool_call_service.produce_governed_tool_call(
                run=run,
                expected_tool=acceptance_tool,
                governed_tools={acceptance_tool},
            )
        except OutwardModelToolCallError as exc:
            return await self._fail_run(run, str(exc))

        tool_call = model_result.tool_call
        tool = tool_call["tool"]
        connector = self.connector_registry.get(tool)
        if connector is None:
            return await self._fail_run(run, f"model tool is not registered: {tool}")
        if tool != acceptance_tool:
            return await self._fail_run(run, f"model tool does not match acceptance_contract tool: {tool}")
        try:
            self.connector_service.validate_args(tool, tool_call["args"])
        except OutwardConnectorArgumentError as exc:
            return await self._fail_run(run, f"invalid model connector args for {tool}: {exc.errors}")

        run_with_model_call = await self._record_model_proposal_event(run, tool, tool_call, model_result, connector.pii_fields)
        try:
            self.connector_service.validate_policy(tool, tool_call["args"])
        except OutwardConnectorPolicyError as exc:
            return await self._policy_reject(run_with_model_call, tool, tool_call, model_result, connector.pii_fields, exc.reason)

        timeout = int(run_with_model_call.policy_overrides.get("approval_timeout_seconds") or connector.timeout_seconds)
        proposal = await self.approval_service.request_tool_approval(
            run_id=run.run_id,
            tool=tool,
            args=tool_call["args"],
            context_summary="model-produced governed tool call from live provider response",
            timeout_seconds=timeout,
        )
        await self.model_tool_call_service.record_proposal_extraction(
            run=run_with_model_call,
            model_result=model_result,
            proposal_id=proposal.proposal_id,
            pii_fields=connector.pii_fields,
            acceptance_result="accepted_for_proposal",
        )
        return replace(run_with_model_call, status="approval_required", pending_proposals=(proposal.to_queue_payload(),))

    async def _record_model_proposal_event(
        self,
        run: OutwardRunRecord,
        tool: str,
        tool_call: dict[str, Any],
        model_result: Any,
        pii_fields: tuple[str, ...],
    ) -> OutwardRunRecord:
        evidence = model_result.model_invocation
        model_invocation_ref = str(evidence.get("model_invocation_ref") or "").strip()
        run_with_model_call = replace(
            run,
            task=task_with_model_tool_call(run, tool_call=tool_call, model_invocation_ref=model_invocation_ref),
        )
        await self.run_store.update(run_with_model_call)
        await self._append_once(
            event_id=step_event_id(run.run_id, run.current_turn, 300, f"proposal:{tool}:{len(run.pending_proposals) + 1:04d}"),
            event_type="proposal_made",
            run=run_with_model_call,
            turn=run.current_turn,
            payload={
                "run_id": run.run_id,
                "namespace": run.namespace,
                "tool": tool,
                "args_preview": redacted_args_preview(tool_call["args"], pii_fields),
                "context_summary": "model-produced governed tool call from live provider response",
                "model_invocation_ref": model_invocation_ref,
                "model_invocation_sha256": str(evidence.get("model_invocation_sha256") or ""),
                "model_response_content_sha256": str(evidence.get("model_response_content_sha256") or ""),
                "proposal_extraction_ref": str(evidence.get("proposal_extraction_ref") or ""),
                "provider_name": evidence.get("provider_name"),
                "model_name": evidence.get("model_name"),
                "tool_name": tool,
                "tool_args_hash": str(evidence.get("tool_args_hash") or args_hash(tool_call["args"])),
            },
        )
        return run_with_model_call

    async def _policy_reject(
        self,
        run: OutwardRunRecord,
        tool: str,
        tool_call: dict[str, Any],
        model_result: Any,
        pii_fields: tuple[str, ...],
        reason: str,
    ) -> OutwardRunRecord:
        await self.model_tool_call_service.record_proposal_extraction(
            run=run,
            model_result=model_result,
            proposal_id=None,
            pii_fields=pii_fields,
            acceptance_result="rejected_by_policy",
        )
        await self._append_once(
            event_id=step_event_id(run.run_id, run.current_turn, 350, f"proposal_policy_rejected:{tool}"),
            event_type="proposal_policy_rejected",
            run=run,
            turn=run.current_turn,
            payload={
                "run_id": run.run_id,
                "tool": tool,
                "args_preview": redacted_args_preview(tool_call["args"], pii_fields),
                "policy_result": "rejected",
                "reason": reason,
                "tool_args_hash": args_hash(tool_call["args"]),
            },
        )
        await self._complete_turn(run, tool, "policy", outcome="policy_rejected")
        return await self._complete_terminal(run, status="completed", stop_reason=reason, outcome="policy_rejected")

    async def _advance_to_next_turn(
        self,
        run: OutwardRunRecord,
        tool: str,
        proposal_id: str,
        steps: list[dict[str, Any]],
    ) -> OutwardRunRecord:
        await self._complete_turn(run, tool, proposal_id, outcome="success")
        next_turn = run.current_turn + 1
        if next_turn > run.max_turns:
            return await self._fail_run(run, "max_turns exceeded before next governed step")
        advanced = replace(run, status="running", current_turn=next_turn, pending_proposals=())
        await self.run_store.update(advanced)
        await self._start_turn(advanced, next_turn)
        next_step = current_step(advanced, steps)
        if next_step is None:
            return await self._complete_terminal(advanced, status="completed", stop_reason=None, outcome="success")
        return await self._handle_model_tool_call(advanced, next_step)

    async def _complete_run(self, run: OutwardRunRecord, tool: str, proposal_id: str) -> OutwardRunRecord:
        await self._complete_turn(run, tool, proposal_id, outcome="success")
        return await self._complete_terminal(run, status="completed", stop_reason=None, outcome="success")

    async def _complete_turn(self, run: OutwardRunRecord, tool: str, proposal_id: str, *, outcome: str) -> None:
        await self._append_once(
            event_id=step_event_id(run.run_id, run.current_turn, 500, f"commitment:{tool}:{proposal_suffix(proposal_id)}"),
            event_type="commitment_recorded",
            run=run,
            turn=run.current_turn,
            payload={"run_id": run.run_id, "tool": tool, "outcome": outcome},
        )
        await self._append_once(
            event_id=step_event_id(run.run_id, run.current_turn, 600, "turn:completed"),
            event_type="turn_completed",
            run=run,
            turn=run.current_turn,
            payload={"run_id": run.run_id, "turn": run.current_turn, "outcome": outcome},
        )

    async def _complete_terminal(
        self,
        run: OutwardRunRecord,
        *,
        status: str,
        stop_reason: str | None,
        outcome: str,
        completed_at: str | None = None,
    ) -> OutwardRunRecord:
        now = completed_at or self.utc_now()
        completed = replace(run, status=status, pending_proposals=(), completed_at=now, stop_reason=stop_reason)
        await self.run_store.update(completed)
        await self._append_once(
            event_id=f"run:{run.run_id}:0700:completed",
            event_type="run_completed",
            run=completed,
            turn=run.current_turn,
            payload={"run_id": run.run_id, "status": status, "outcome": outcome, "completed_at": now},
        )
        return completed

    async def _fail_run(self, run: OutwardRunRecord, reason: str) -> OutwardRunRecord:
        now = self.utc_now()
        failed = replace(run, status="failed", pending_proposals=(), completed_at=now, stop_reason=reason)
        await self.run_store.update(failed)
        await self._append_once(
            event_id=f"run:{run.run_id}:0900:failed",
            event_type="run_failed",
            run=failed,
            turn=run.current_turn,
            payload={"run_id": run.run_id, "status": "failed", "reason": reason, "completed_at": now},
        )
        return failed

    async def _start_turn(self, run: OutwardRunRecord, turn: int) -> None:
        await self._append_once(
            event_id=step_event_id(run.run_id, turn, 200, "turn:started"),
            event_type="turn_started",
            run=run,
            turn=turn,
            payload={"run_id": run.run_id, "turn": turn, "agent_id": "outward-agent"},
        )

    async def _require_run(self, run_id: str) -> OutwardRunRecord:
        run = await self.run_store.get(str(run_id or "").strip())
        if run is None:
            raise OutwardRunExecutionError(f"Run '{run_id}' not found")
        return run

    async def _append_once(
        self,
        *,
        event_id: str,
        event_type: str,
        run: OutwardRunRecord,
        turn: int,
        payload: dict[str, Any],
    ) -> None:
        if await self.event_store.get(event_id) is not None:
            return
        await self.event_store.append(
            LedgerEvent(event_id=event_id, event_type=event_type, run_id=run.run_id, turn=turn, agent_id="outward-agent", at=self.utc_now(), payload=payload)
        )


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
