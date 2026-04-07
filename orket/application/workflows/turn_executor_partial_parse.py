from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orket.core.domain.execution import ExecutionTurn
from orket.logging import log_event
from orket.schema import IssueConfig, RoleConfig

if TYPE_CHECKING:
    from .turn_executor import TurnExecutor, TurnResult
    from .turn_executor_model_flow import FailedResultFactory, FailureEmitter


def partial_parse_recovery_policy(context: dict[str, Any]) -> str:
    policy = str(context.get("partial_parse_recovery_policy") or "escalate").strip().lower()
    return "retry" if policy == "retry" else "escalate"


async def blocked_partial_parse_failure(
    *,
    executor: TurnExecutor,
    issue: IssueConfig,
    role: RoleConfig,
    context: dict[str, Any],
    session_id: str,
    turn_index: int,
    turn_trace_id: str,
    turn: ExecutionTurn,
    emit_failure: FailureEmitter,
    turn_result_failed: FailedResultFactory,
) -> tuple[ExecutionTurn | None, str, TurnResult | None]:
    reason = turn.error or "tool-call recovery was partial"
    log_event(
        "turn_failed",
        {
            "issue_id": issue.id,
            "role": role.name,
            "session_id": session_id,
            "turn_index": turn_index,
            "turn_trace_id": turn_trace_id,
            "type": "partial_parse_failure",
            "error": reason,
            "partial_parse_recovery_policy": partial_parse_recovery_policy(context),
        },
        executor.workspace,
    )
    await emit_failure(reason, "partial_parse_failure", turn)
    result = turn_result_failed(reason, False)
    result.turn = turn
    return None, "", result
