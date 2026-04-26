from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import BuiltInConnectorRegistry
from orket.application.services.outward_connector_service import (
    OutwardConnectorArgumentError,
    OutwardConnectorNotFoundError,
    OutwardConnectorService,
)
from orket.application.services.outward_approval_service import (
    OutwardApprovalService,
    redacted_args_preview,
)
from orket.application.services.outward_model_tool_call_service import (
    OutwardModelToolCallError,
    OutwardModelToolCallService,
)
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord

_EXPLICIT_TOOL_CALL_KEY = "governed_tool_call"
_MODEL_TOOL_CALL_KEY = "model_governed_tool_call"


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
        acceptance_tool_call = _acceptance_tool_call(run)
        if acceptance_tool_call is None or run.status != "queued":
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
        await self._append_once(
            event_id=f"run:{run.run_id}:0200:turn:1:started",
            event_type="turn_started",
            run=started,
            turn=1,
            payload={"run_id": run.run_id, "turn": 1, "agent_id": "outward-agent"},
        )
        return await self._handle_model_tool_call(started, acceptance_tool_call)

    async def continue_after_approval(self, proposal_id: str) -> OutwardRunRecord:
        proposal = await self.approval_service.get(proposal_id)
        if proposal is None:
            raise OutwardRunExecutionError(f"Approval proposal '{proposal_id}' not found")
        run = await self._require_run(proposal.run_id)
        if run.status in {"completed", "failed"}:
            return run
        if proposal.status != "approved":
            return run

        tool_call = _model_tool_call(run)
        if tool_call is None:
            return await self._fail_run(run, "approved proposal has no recorded model governed tool call")
        if tool_call["tool"] != proposal.tool:
            return await self._fail_run(run, f"approved proposal tool drifted from model tool: {proposal.tool}")

        try:
            tool_event_payload = await self.connector_service.invoke(proposal.tool, tool_call["args"])
        except OutwardConnectorArgumentError as exc:
            tool_event_payload = _invalid_args_event_payload(proposal.tool, tool_call["args"], exc.errors)
        except OutwardConnectorNotFoundError as exc:
            tool_event_payload = _failed_tool_event_payload(proposal.tool, tool_call["args"], str(exc))
        outcome = str(tool_event_payload.get("outcome") or "failed")
        await self._append_once(
            event_id=f"run:{run.run_id}:0400:tool:{proposal.tool}",
            event_type="tool_invoked",
            run=run,
            turn=1,
            payload=tool_event_payload,
        )
        if outcome != "success":
            return await self._fail_run(run, _failure_reason(tool_event_payload))
        return await self._complete_run(run, proposal.tool)

    async def _handle_model_tool_call(
        self,
        run: OutwardRunRecord,
        acceptance_tool_call: dict[str, Any],
    ) -> OutwardRunRecord:
        acceptance_tool = acceptance_tool_call["tool"]
        if self.connector_registry.get(acceptance_tool) is None:
            return await self._fail_run(run, f"acceptance_contract tool is not registered: {acceptance_tool}")
        governed_tools = {str(tool).strip() for tool in (run.policy_overrides.get("approval_required_tools") or [])}
        if acceptance_tool not in governed_tools:
            return await self._fail_run(run, f"acceptance_contract tool is not approval-required: {acceptance_tool}")
        try:
            model_result = await self.model_tool_call_service.produce_governed_tool_call(
                run=run,
                expected_tool=acceptance_tool,
                governed_tools=governed_tools,
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
        if tool not in governed_tools:
            return await self._fail_run(run, f"model tool is not approval-required for this run: {tool}")
        try:
            self.connector_service.validate_args(tool, tool_call["args"])
        except OutwardConnectorArgumentError as exc:
            return await self._fail_run(run, f"invalid model connector args for {tool}: {exc.errors}")

        model_invocation_ref = str(model_result.model_invocation.get("model_invocation_ref") or "").strip()
        model_invocation_sha256 = str(model_result.model_invocation.get("model_invocation_sha256") or "").strip()
        model_response_content_sha256 = str(
            model_result.model_invocation.get("model_response_content_sha256") or ""
        ).strip()
        proposal_extraction_ref = str(model_result.model_invocation.get("proposal_extraction_ref") or "").strip()
        tool_args_hash = str(model_result.model_invocation.get("tool_args_hash") or _args_hash(tool_call["args"]))
        model_recorded_task = dict(run.task)
        model_recorded_task[_MODEL_TOOL_CALL_KEY] = {
            "tool": tool,
            "args": dict(tool_call["args"]),
            "source": "model_output",
            "model_invocation_ref": model_invocation_ref,
        }
        run_with_model_call = replace(run, task=model_recorded_task)
        await self.run_store.update(run_with_model_call)

        await self._append_once(
            event_id=f"run:{run.run_id}:0300:proposal:{tool}",
            event_type="proposal_made",
            run=run_with_model_call,
            turn=1,
            payload={
                "run_id": run.run_id,
                "namespace": run.namespace,
                "tool": tool,
                "args_preview": redacted_args_preview(tool_call["args"], connector.pii_fields),
                "context_summary": "model-produced governed tool call from live provider response",
                "model_invocation_ref": model_invocation_ref,
                "model_invocation_sha256": model_invocation_sha256,
                "model_response_content_sha256": model_response_content_sha256,
                "proposal_extraction_ref": proposal_extraction_ref,
                "provider_name": model_result.model_invocation.get("provider_name"),
                "model_name": model_result.model_invocation.get("model_name"),
                "tool_name": tool,
                "tool_args_hash": tool_args_hash,
            },
        )
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
        )
        return replace(
            run_with_model_call,
            status="approval_required",
            pending_proposals=(proposal.to_queue_payload(),),
        )

    async def _complete_run(self, run: OutwardRunRecord, tool: str) -> OutwardRunRecord:
        now = self.utc_now()
        await self._append_once(
            event_id=f"run:{run.run_id}:0500:commitment:{tool}",
            event_type="commitment_recorded",
            run=run,
            turn=1,
            payload={"run_id": run.run_id, "tool": tool, "outcome": "committed"},
        )
        await self._append_once(
            event_id=f"run:{run.run_id}:0600:turn:1:completed",
            event_type="turn_completed",
            run=run,
            turn=1,
            payload={"run_id": run.run_id, "turn": 1, "outcome": "success"},
        )
        completed = replace(run, status="completed", pending_proposals=(), completed_at=now, stop_reason=None)
        await self.run_store.update(completed)
        await self._append_once(
            event_id=f"run:{run.run_id}:0700:completed",
            event_type="run_completed",
            run=completed,
            turn=1,
            payload={"run_id": run.run_id, "status": "completed", "completed_at": now},
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
            LedgerEvent(
                event_id=event_id,
                event_type=event_type,
                run_id=run.run_id,
                turn=turn,
                agent_id="outward-agent",
                at=self.utc_now(),
                payload=payload,
            )
        )


def _acceptance_tool_call(run: OutwardRunRecord) -> dict[str, Any] | None:
    acceptance_contract = run.task.get("acceptance_contract")
    if not isinstance(acceptance_contract, Mapping):
        return None
    raw = acceptance_contract.get(_EXPLICIT_TOOL_CALL_KEY)
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise OutwardRunExecutionValidationError("task.acceptance_contract.governed_tool_call must be an object")
    tool = str(raw.get("tool") or "").strip()
    args = raw.get("args")
    if not tool:
        raise OutwardRunExecutionValidationError("task.acceptance_contract.governed_tool_call.tool is required")
    if not isinstance(args, Mapping):
        raise OutwardRunExecutionValidationError("task.acceptance_contract.governed_tool_call.args must be an object")
    return {"tool": tool, "args": dict(args)}


def _model_tool_call(run: OutwardRunRecord) -> dict[str, Any] | None:
    raw = run.task.get(_MODEL_TOOL_CALL_KEY)
    if not isinstance(raw, Mapping):
        return None
    tool = str(raw.get("tool") or "").strip()
    args = raw.get("args")
    if not tool or not isinstance(args, Mapping):
        return None
    return {"tool": tool, "args": dict(args)}


def _args_hash(args: dict[str, Any]) -> str:
    payload = json.dumps(args, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _invalid_args_event_payload(tool: str, args: dict[str, Any], errors: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "connector_name": tool,
        "args_hash": _args_hash(args),
        "result_summary": {"ok": False, "error": "invalid_args", "errors": errors},
        "duration_ms": 0,
        "outcome": "failed",
    }


def _failed_tool_event_payload(tool: str, args: dict[str, Any], error: str) -> dict[str, Any]:
    return {
        "connector_name": tool,
        "args_hash": _args_hash(args),
        "result_summary": {"ok": False, "error": error},
        "duration_ms": 0,
        "outcome": "failed",
    }


def _failure_reason(tool_event_payload: dict[str, Any]) -> str:
    summary = tool_event_payload.get("result_summary")
    if isinstance(summary, dict) and str(summary.get("error") or "").strip():
        return str(summary["error"])
    return f"connector invocation {tool_event_payload.get('outcome') or 'failed'}"


__all__ = [
    "OutwardRunExecutionError",
    "OutwardRunExecutionService",
    "OutwardRunExecutionValidationError",
]
