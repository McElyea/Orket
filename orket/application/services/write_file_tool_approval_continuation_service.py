from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orket.application.services.turn_tool_control_plane_closeout import finalize_turn_execution
from orket.application.services.turn_tool_control_plane_support import run_id_for
from orket.core.domain import AttemptState, RunState


def supports_write_file_approval_continuation(
    *,
    tool_name: str,
    context: Mapping[str, Any],
    issue_id: str,
) -> bool:
    return (
        str(tool_name or "").strip() == "write_file"
        and str(context.get("stage_gate_mode") or "").strip() == "approval_required"
        and str(context.get("run_namespace_scope") or "").strip() == f"issue:{issue_id}"
    )


class WriteFileToolApprovalContinuationService:
    """Continue or stop the bounded `write_file` approval slice on the same governed run."""

    def __init__(self, *, execution_repository: Any, publication: Any) -> None:
        self.execution_repository = execution_repository
        self.publication = publication

    @staticmethod
    def supports_resolution(approval: Mapping[str, object]) -> bool:
        payload = approval.get("payload")
        if not isinstance(payload, Mapping):
            return False
        return (
            str(approval.get("request_type") or "").strip() == "tool_approval"
            and str(approval.get("reason") or "").strip() == "approval_required_tool:write_file"
            and str(payload.get("tool") or "").strip() == "write_file"
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
            raise RuntimeError("write_file approval continuation requires payload mapping")

        control_plane_target_ref = str(payload.get("control_plane_target_ref") or "").strip()
        turn_index = payload.get("turn_index")
        if not control_plane_target_ref or not isinstance(turn_index, int):
            raise RuntimeError("write_file approval continuation requires target_ref and integer turn_index")

        expected_target_ref = run_id_for(
            session_id=session_id,
            issue_id=issue_id,
            role_name=seat_name,
            turn_index=turn_index,
        )
        if control_plane_target_ref != expected_target_ref:
            raise RuntimeError(
                "write_file approval continuation target_ref drifted from the admitted governed run identity"
            )

        run = await self.execution_repository.get_run_record(run_id=control_plane_target_ref)
        if run is None:
            if getattr(engine, "_pipeline", None) is None:
                return None
            raise RuntimeError("write_file approval continuation target run is missing")
        if str(run.namespace_scope or "").strip() != f"issue:{issue_id}":
            raise RuntimeError("write_file approval continuation namespace scope drifted from issue authority")
        existing_truth = await self.publication.repository.get_final_truth(run_id=control_plane_target_ref)
        if run.final_truth_record_id is not None or existing_truth is not None:
            return None
        if run.lifecycle_state is not RunState.EXECUTING:
            raise RuntimeError("write_file approval continuation requires an unfinished executing governed run")

        current_attempt_id = str(run.current_attempt_id or "").strip()
        if not current_attempt_id:
            raise RuntimeError("write_file approval continuation target run is missing current_attempt_id")
        attempt = await self.execution_repository.get_attempt_record(attempt_id=current_attempt_id)
        if attempt is None or attempt.attempt_state is not AttemptState.EXECUTING:
            raise RuntimeError("write_file approval continuation requires an executing current attempt")

        if status == "DENIED":
            return await finalize_turn_execution(
                execution_repository=self.execution_repository,
                publication=self.publication,
                run=run,
                attempt=attempt,
                authoritative_result_ref=f"approval-request:{approval_id}:denied",
                violation_reasons=["Approval denied for tool 'write_file' before execution."],
                executed_step_count=0,
                error_type=RuntimeError,
            )

        if status != "APPROVED":
            raise RuntimeError("write_file approval continuation requires approved or denied resolution")

        run_issue = getattr(engine, "run_issue", None)
        if not callable(run_issue) or getattr(engine, "_pipeline", None) is None:
            return None
        return await run_issue(
            issue_id,
            session_id=session_id,
        )


__all__ = [
    "WriteFileToolApprovalContinuationService",
    "supports_write_file_approval_continuation",
]
