from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .turn_executor import TurnExecutor


async def emit_turn_failure_traces(
    *,
    executor: TurnExecutor,
    context: dict[str, Any],
    role_name: str,
    session_id: str,
    issue_id: str,
    turn_index: int,
    issue: Any,
    role: Any,
    current_turn: Any,
    error: str,
    failure_type: str,
) -> None:
    executor.artifact_writer.append_memory_event(
        context,
        role_name=role_name,
        interceptor="on_turn_failure",
        decision_type=str(failure_type).strip() or "turn_failed",
    )
    await asyncio.to_thread(
        executor.artifact_writer.emit_memory_traces,
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index,
        issue=issue,
        role=role,
        context=context,
        turn=current_turn,
        failure_reason=str(error or "").strip() or "turn_failed",
        failure_type=str(failure_type or "").strip() or "turn_failed",
    )
