from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from orket.logging import log_event
from orket.application.services.turn_tool_control_plane_recovery import TurnToolCheckpointRecoveryError
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.core.domain.state_machine import StateMachineError
from orket.schema import IssueConfig, RoleConfig
from .prompt_budget_guard import maybe_record_prompt_budget
from .turn_executor_completed_replay import load_completed_turn_replay_if_needed
from .turn_executor_control_plane import (
    ensure_turn_control_plane_reentry_allowed_if_needed,
    write_turn_checkpoint_and_publish_if_needed,
)
from .turn_executor_model_flow import prepare_turn_for_execution
from .turn_failure_traces import emit_turn_failure_traces
from .turn_executor_runtime import (
    invoke_model_complete as _invoke_model_complete,
    runtime_tokens_payload as _runtime_tokens_payload,
    state_delta_from_tool_calls as _state_delta_from_tool_calls,
    synthesize_required_status_tool_call as _synthesize_required_status_tool_call,
)

if TYPE_CHECKING:
    from .turn_executor import TurnExecutor

runtime_tokens_payload = _runtime_tokens_payload
state_delta_from_tool_calls = _state_delta_from_tool_calls
synthesize_required_status_tool_call = _synthesize_required_status_tool_call


async def execute_turn(
    executor: TurnExecutor,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    toolbox: Any,
    context: Dict[str, Any],
    system_prompt: Optional[str] = None,
):
    from .turn_executor import ModelTimeoutError, ToolApprovalPendingError, ToolValidationError, TurnResult

    issue_id = issue.id
    role_name = role.name
    session_id = context.get("session_id", "unknown-session")
    turn_index = int(context.get("turn_index", 0))
    turn_trace_id = f"{session_id}:{issue_id}:{role_name}:{turn_index}"
    started_at = time.perf_counter()
    current_turn = None
    prompt_hash = ""

    async def emit_failure(error: str, failure_type: str, turn_override: Any = None) -> None:
        await emit_turn_failure_traces(
            executor=executor,
            context=context,
            role_name=role_name,
            session_id=session_id,
            issue_id=issue_id,
            turn_index=turn_index,
            issue=issue,
            role=role,
            current_turn=current_turn if turn_override is None else turn_override,
            error=error,
            failure_type=failure_type,
        )

    try:
        if executor.artifact_writer.memory_trace_enabled(context):
            context["_memory_trace_events"] = []
        executor._validate_preconditions(issue, role, context)
        await ensure_turn_control_plane_reentry_allowed_if_needed(
            executor=executor,
            issue_id=issue_id,
            role_name=role_name,
            context=context,
        )
        completed_replay_turn = await load_completed_turn_replay_if_needed(
            executor=executor,
            issue_id=issue_id,
            role_name=role_name,
            context=context,
        )
        if completed_replay_turn is not None:
            current_turn = completed_replay_turn
            log_event(
                "turn_complete",
                {
                    "issue_id": issue_id,
                    "role": role_name,
                    "tool_calls": len(completed_replay_turn.tool_calls),
                    "tokens": runtime_tokens_payload(completed_replay_turn),
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "turn_trace_id": turn_trace_id,
                    "replayed_from_control_plane": True,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                },
                executor.workspace,
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
                turn=completed_replay_turn,
            )
            return TurnResult.succeeded(completed_replay_turn)
        turn, prompt_hash, early_result = await prepare_turn_for_execution(
            executor=executor,
            issue=issue,
            role=role,
            model_client=model_client,
            context=context,
            system_prompt=system_prompt,
            session_id=session_id,
            turn_index=turn_index,
            turn_trace_id=turn_trace_id,
            emit_failure=emit_failure,
            turn_result_failed=TurnResult.failed,
        )
        if early_result is not None:
            return early_result
        assert turn is not None
        current_turn = turn

        await asyncio.to_thread(
            executor.artifact_writer.write_turn_artifact,
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            filename="parsed_tool_calls.json",
            content=json.dumps(
                [{"tool": tool_call.tool, "args": tool_call.args} for tool_call in turn.tool_calls],
                indent=2,
                ensure_ascii=False,
            ),
        )
        await write_turn_checkpoint_and_publish_if_needed(
            executor=executor,
            turn=turn,
            context=context,
            prompt_hash=prompt_hash,
        )

        if turn.tool_calls:
            await executor.tool_dispatcher.execute_tools(
                turn=turn,
                toolbox=toolbox,
                context=context,
                issue=issue,
            )
        else:
            log_event(
                "turn_no_tool_calls",
                {
                    "issue_id": issue_id,
                    "role": role_name,
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "turn_trace_id": turn_trace_id,
                    "response_preview": (turn.content or "")[:240],
                },
                executor.workspace,
            )

        log_event(
            "turn_complete",
            {
                "issue_id": issue_id,
                "role": role_name,
                "tool_calls": len(turn.tool_calls),
                "tokens": runtime_tokens_payload(turn),
                "session_id": session_id,
                "turn_index": turn_index,
                "turn_trace_id": turn_trace_id,
                "local_prompt_profile_id": str((turn.raw or {}).get("profile_id") or ""),
                "local_prompt_task_class": str((turn.raw or {}).get("task_class") or ""),
                "local_prompting_mode": str((turn.raw or {}).get("local_prompting_mode") or ""),
                "execution_profile": context.get("execution_profile"),
                "builder_seat_choice": context.get("builder_seat_choice"),
                "reviewer_seat_choice": context.get("reviewer_seat_choice"),
                "seat_coercion": context.get("seat_coercion"),
                "artifact_contract": context.get("artifact_contract"),
                "odr_active": bool(context.get("odr_active")),
                "odr_valid": context.get("odr_valid"),
                "odr_pending_decisions": context.get("odr_pending_decisions"),
                "odr_stop_reason": context.get("odr_stop_reason"),
                "odr_artifact_path": context.get("odr_artifact_path"),
                "replayed_from_control_plane": bool(
                    (turn.raw or {}).get("control_plane_resume", {}).get("artifact_reused")
                ),
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
            },
            executor.workspace,
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
            turn=turn,
        )
        return TurnResult.succeeded(turn)

    except StateMachineError as exc:
        executor.middleware.apply_on_turn_failure(exc, issue=issue, role=role, context=context)
        log_event(
            "turn_failed",
            {
                "issue_id": issue_id,
                "error": str(exc),
                "type": "state_violation",
                "session_id": session_id,
                "turn_index": turn_index,
                "turn_trace_id": turn_trace_id,
            },
            executor.workspace,
        )
        await emit_failure(str(exc), "state_violation")
        return TurnResult.failed(f"State violation: {exc}", should_retry=False)

    except ToolValidationError as exc:
        executor.middleware.apply_on_turn_failure(exc, issue=issue, role=role, context=context)
        log_event(
            "turn_failed",
            {
                "issue_id": issue_id,
                "error": str(exc),
                "type": "tool_violation",
                "session_id": session_id,
                "turn_index": turn_index,
                "turn_trace_id": turn_trace_id,
            },
            executor.workspace,
        )
        await emit_failure(str(exc), "tool_violation")
        return TurnResult.governance_violation(exc.violations)

    except ToolApprovalPendingError as exc:
        executor.middleware.apply_on_turn_failure(exc, issue=issue, role=role, context=context)
        log_event(
            "turn_failed",
            {
                "issue_id": issue_id,
                "error": str(exc),
                "type": "tool_approval_pending",
                "session_id": session_id,
                "turn_index": turn_index,
                "turn_trace_id": turn_trace_id,
            },
            executor.workspace,
        )
        await emit_failure(str(exc), "tool_approval_pending")
        return TurnResult.failed(str(exc), should_retry=True)

    except (TurnToolControlPlaneError, TurnToolCheckpointRecoveryError) as exc:
        executor.middleware.apply_on_turn_failure(exc, issue=issue, role=role, context=context)
        log_event(
            "turn_failed",
            {
                "issue_id": issue_id,
                "error": str(exc),
                "type": "control_plane_blocked",
                "session_id": session_id,
                "turn_index": turn_index,
                "turn_trace_id": turn_trace_id,
            },
            executor.workspace,
        )
        await emit_failure(str(exc), "control_plane_blocked")
        return TurnResult.failed(str(exc), should_retry=False)

    except ModelTimeoutError as exc:
        executor.middleware.apply_on_turn_failure(exc, issue=issue, role=role, context=context)
        log_event(
            "turn_failed",
            {
                "issue_id": issue_id,
                "error": str(exc),
                "type": "timeout",
                "session_id": session_id,
                "turn_index": turn_index,
                "turn_trace_id": turn_trace_id,
            },
            executor.workspace,
        )
        await emit_failure(str(exc), "timeout")
        return TurnResult.failed(str(exc), should_retry=True)

    except (ValueError, TypeError, KeyError, RuntimeError, OSError, AttributeError) as exc:
        import traceback

        executor.middleware.apply_on_turn_failure(exc, issue=issue, role=role, context=context)
        log_event(
            "turn_failed",
            {
                "issue_id": issue_id,
                "error": str(exc),
                "type": type(exc).__name__,
                "traceback": traceback.format_exc(),
                "session_id": session_id,
                "turn_index": turn_index,
                "turn_trace_id": turn_trace_id,
            },
            executor.workspace,
        )
        await emit_failure(str(exc), type(exc).__name__)
        return TurnResult.failed(f"Unexpected error: {exc}", should_retry=False)
