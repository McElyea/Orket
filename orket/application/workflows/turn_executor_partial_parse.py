from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orket.core.domain.execution import ExecutionTurn
from orket.logging import log_event

from .turn_artifact_destination import TurnArtifactDestination

if TYPE_CHECKING:
    from .turn_executor import TurnResult
    from .turn_executor_model_flow import FailedResultFactory, FailureEmitter


def partial_parse_recovery_policy(context: dict[str, Any]) -> str:
    policy = str(context.get("partial_parse_recovery_policy") or "escalate").strip().lower()
    return "retry" if policy == "retry" else "escalate"


async def blocked_partial_parse_failure(
    *,
    destination: TurnArtifactDestination,
    context: dict[str, Any],
    turn_trace_id: str,
    turn: ExecutionTurn,
    emit_failure: FailureEmitter,
    turn_result_failed: FailedResultFactory,
) -> tuple[ExecutionTurn | None, str, TurnResult | None]:
    reason = turn.error or "tool-call recovery was partial"
    log_event(
        "turn_failed",
        {
            "issue_id": destination.issue_id,
            "role": destination.role_name,
            "session_id": destination.session_id,
            "turn_index": destination.turn_index,
            "turn_trace_id": turn_trace_id,
            "type": "partial_parse_failure",
            "error": reason,
            "partial_parse_recovery_policy": partial_parse_recovery_policy(context),
        },
        destination.workspace,
    )
    await emit_failure(reason, "partial_parse_failure", turn)
    result = turn_result_failed(reason, False)
    result.turn = turn
    return None, "", result
