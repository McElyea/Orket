from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.turn_tool_control_plane_closeout import finalize_turn_execution_atomic
from orket.application.services.turn_tool_control_plane_state_gate import (
    require_resolved_tool_dispatches,
    require_turn_dispatch_contract,
    require_turn_tool_resource_authority,
)
from orket.application.services.turn_tool_control_plane_support import run_id_for
from orket.core.domain import AttemptState, RunState
from orket.core.domain.control_plane_final_truth import validate_terminal_record_consistency

ADMITTED_GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_TOOLS = frozenset(
    {
        "create_directory",
        "create_issue",
        "write_file",
    }
)


def supports_governed_turn_tool_approval_continuation(
    *,
    tool_name: str,
    context: Mapping[str, Any],
    issue_id: str,
) -> bool:
    normalized_tool = str(tool_name or "").strip()
    return (
        normalized_tool in ADMITTED_GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_TOOLS
        and str(context.get("stage_gate_mode") or "").strip() == "approval_required"
        and str(context.get("run_namespace_scope") or "").strip() == f"issue:{issue_id}"
    )


class GovernedTurnToolApprovalContinuationService:
    """Continue or stop one admitted governed turn-tool approval slice on the same governed run."""

    def __init__(self, *, execution_repository: Any, publication: Any, transactions: Any) -> None:
        if transactions is None:
            raise RuntimeError("governed turn-tool approval continuation requires transaction ownership")
        self.execution_repository = execution_repository
        self.publication = publication
        self.transactions = transactions

    @staticmethod
    def supports_resolution(approval: Mapping[str, object]) -> bool:
        payload = approval.get("payload")
        if not isinstance(payload, Mapping):
            return False
        tool_name = str(payload.get("tool") or "").strip()
        expected_reason = f"approval_required_tool:{tool_name}"
        return (
            tool_name in ADMITTED_GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_TOOLS
            and str(approval.get("request_type") or "").strip() == "tool_approval"
            and str(approval.get("reason") or "").strip() == expected_reason
        )

    async def continue_or_stop(self, *, engine: Any, resolved_approval: Mapping[str, object]) -> Any:
        if not self.supports_resolution(resolved_approval):
            return None
        approval_id = str(
            resolved_approval.get("approval_id") or resolved_approval.get("request_id") or ""
        ).strip()
        session_id = str(resolved_approval.get("session_id") or "").strip()
        issue_id = str(resolved_approval.get("issue_id") or "").strip()
        seat_name = str(resolved_approval.get("seat_name") or "").strip()
        status = str(resolved_approval.get("status") or "").strip().upper()
        payload = resolved_approval.get("payload")
        if not isinstance(payload, Mapping):
            raise RuntimeError("governed turn-tool approval continuation requires payload mapping")

        tool_name = str(payload.get("tool") or "").strip()
        if tool_name not in ADMITTED_GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_TOOLS:
            return None

        control_plane_target_ref = str(payload.get("control_plane_target_ref") or "").strip()
        turn_index = payload.get("turn_index")
        if not control_plane_target_ref or not isinstance(turn_index, int):
            raise RuntimeError(
                f"{tool_name} approval continuation requires target_ref and integer turn_index"
            )

        expected_target_ref = run_id_for(
            session_id=session_id,
            issue_id=issue_id,
            role_name=seat_name,
            turn_index=turn_index,
        )
        if control_plane_target_ref != expected_target_ref:
            raise RuntimeError(
                f"{tool_name} approval continuation target_ref drifted from the admitted governed run identity"
            )

        run, attempt, existing_truth = await read_approval_execution(
            transactions=self.transactions, publication=self.publication, target=control_plane_target_ref)
        if run is None:
            if getattr(engine, "_pipeline", None) is None:
                return None
            raise RuntimeError(f"{tool_name} approval continuation target run is missing")
        if str(run.namespace_scope or "").strip() != f"issue:{issue_id}":
            raise RuntimeError(f"{tool_name} approval continuation namespace scope drifted from issue authority")
        if existing_truth is not None:
            return await self._resume_epic(engine, session_id, approval_id, finished_child=True)
        if run.lifecycle_state is not RunState.EXECUTING:
            raise RuntimeError(
                f"{tool_name} approval continuation requires an unfinished executing governed run"
            )

        if not run.current_attempt_id:
            raise RuntimeError(f"{tool_name} approval continuation target run is missing current_attempt_id")
        if attempt is None or attempt.attempt_state is not AttemptState.EXECUTING:
            raise RuntimeError(f"{tool_name} approval continuation requires an executing current attempt")

        if status == "DENIED":
            await stop_approval_execution(
                transactions=self.transactions,
                publication=self.publication,
                run=run,
                attempt=attempt,
                authoritative_result_ref=f"approval-request:{approval_id}:denied",
                violation_reasons=[f"Approval denied for tool '{tool_name}' before execution."],
            )

        if status not in {"APPROVED", "DENIED"}:
            raise RuntimeError(f"{tool_name} approval continuation requires approved or denied resolution")

        return await self._resume_epic(engine, session_id, approval_id)

    @staticmethod
    async def _resume_epic(engine: Any, session_id: str, approval_id: str, *, finished_child: bool = False) -> Any:
        if getattr(engine, "_pipeline", None) is None:
            return None
        return await engine._pipeline.resume_epic_approval(
            session_id=session_id, approval_id=approval_id, **({"finished_child": True} if finished_child else {}))


async def read_approval_execution(*, transactions, publication, target):
    """Read the child join together; terminal records do not substitute for released authority."""
    async with transactions() as transaction:
        run = await transaction.execution.get_run_record(run_id=target)
        if run is None:
            return None, None, None
        attempt = (await transaction.execution.get_attempt_record(attempt_id=run.current_attempt_id)
                   if run.current_attempt_id is not None else None)
        truth = await transaction.records.get_final_truth(run_id=target)
        if validate_terminal_record_consistency(run, attempt, truth):
            await require_resolved_tool_dispatches(transaction.execution, run, RuntimeError)
            await require_turn_tool_resource_authority(
                publication=ControlPlanePublicationService(repository=transaction.records, authority=publication.authority),
                run=run, error_type=RuntimeError)
        else:
            await require_turn_dispatch_contract(transaction.records, run, RuntimeError)
        return run, attempt, truth


async def stop_approval_execution(*, transactions, publication, run, attempt,
                                 authoritative_result_ref, violation_reasons):
    return await finalize_turn_execution_atomic(
        transactions=transactions, authority=publication.authority, run_id=run.run_id, attempt_id=attempt.attempt_id,
        authoritative_result_ref=authoritative_result_ref, violation_reasons=violation_reasons,
        executed_step_count=None, error_type=RuntimeError)


__all__ = [
    "ADMITTED_GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_TOOLS",
    "GovernedTurnToolApprovalContinuationService",
    "supports_governed_turn_tool_approval_continuation",
]
