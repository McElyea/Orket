from __future__ import annotations

import json
import time
from functools import partial
from typing import TYPE_CHECKING, Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.card_completion_turn_service import verify_turn_completion_claims
from orket.application.services.turn_tool_control_plane_recovery import TurnToolCheckpointRecoveryError
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.core.domain.state_machine import StateMachineError
from orket.logging import log_event
from orket.schema import IssueConfig, RoleConfig

from .turn_artifact_destination import TurnArtifactDestination
from .turn_control_plane_binding import TurnControlPlaneBinding
from .turn_executor_completed_replay import load_completed_turn_replay_if_needed
from .turn_executor_control_plane import (
    ensure_turn_control_plane_reentry_allowed_if_needed,
    write_turn_checkpoint_and_publish_if_needed,
)
from .turn_executor_model_flow import prepare_turn_for_execution
from .turn_executor_runtime import (
    runtime_tokens_payload as _runtime_tokens_payload,
)
from .turn_executor_runtime import (
    state_delta_from_tool_calls as _state_delta_from_tool_calls,
)
from .turn_executor_runtime import (
    synthesize_required_status_tool_call as _synthesize_required_status_tool_call,
)
from .turn_failure_traces import emit_turn_failure_traces, emit_turn_memory_traces
from .turn_memory_trace_artifacts import MemoryTraceInputs, admit_memory_trace_event_sink

if TYPE_CHECKING:
    from .turn_executor import TurnExecutor, TurnResult

runtime_tokens_payload = _runtime_tokens_payload
state_delta_from_tool_calls = _state_delta_from_tool_calls
synthesize_required_status_tool_call = _synthesize_required_status_tool_call


async def execute_turn(
    executor: TurnExecutor,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    toolbox: Any,
    context: dict[str, Any],
    system_prompt: str | None = None,
    *, destination: TurnArtifactDestination, memory_inputs: MemoryTraceInputs,
    control_plane: TurnControlPlaneBinding,
) -> TurnResult:
    from .turn_executor import (
        ModelConnectionError,
        ModelProviderError,
        ModelTimeoutError,
        ToolApprovalPendingError,
        ToolValidationError,
        TurnResult,
    )

    issue_id, role_name = destination.issue_id, destination.role_name
    session_id, turn_index = destination.session_id, destination.turn_index
    turn_trace_id = f"{session_id}:{issue_id}:{role_name}:{turn_index}"
    started_at = time.perf_counter()
    current_turn = None
    prompt_hash = ""
    memory_events = admit_memory_trace_event_sink(inputs=memory_inputs, context=context)

    def adopt_dispatch_turn(captured_turn: Any) -> None:
        nonlocal current_turn
        current_turn = captured_turn

    async def emit_failure(error: str, failure_type: str, turn_override: Any = None) -> None:
        await emit_turn_failure_traces(
            destination=destination, memory_inputs=memory_inputs, memory_events=memory_events,
            context=context,
            current_turn=current_turn if turn_override is None else turn_override,
            error=error,
            failure_type=failure_type,
        )

    try:
        executor._validate_preconditions(issue, role, context)
        await ensure_turn_control_plane_reentry_allowed_if_needed(
            control_plane=control_plane,
            destination=destination,
        )
        completed_replay_turn = await load_completed_turn_replay_if_needed(
            control_plane=control_plane,
            destination=destination,
        )
        if completed_replay_turn is not None:
            await verify_turn_completion_claims(toolbox=toolbox, turn=completed_replay_turn, context=context)
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
                destination.workspace,
            )
            await emit_turn_memory_traces(
                destination=destination, memory_inputs=memory_inputs, memory_events=memory_events,
                context=context, current_turn=completed_replay_turn,
            )
            return TurnResult.succeeded(completed_replay_turn)
        turn, prompt_hash, early_result = await prepare_turn_for_execution(
            executor=executor,
            control_plane=control_plane,
            destination=destination, memory_events=memory_events,
            issue=issue,
            role=role,
            model_client=model_client,
            context=context,
            system_prompt=system_prompt,
            turn_trace_id=turn_trace_id,
            emit_failure=emit_failure,
            turn_result_failed=TurnResult.failed,
        )
        if early_result is not None:
            return early_result
        assert turn is not None
        current_turn = turn

        await run_owned_thread(partial(
            destination.writer.write_turn_artifact, destination=destination,
            filename="parsed_tool_calls.json",
            content=json.dumps(
                [{"tool": tool_call.tool, "args": tool_call.args} for tool_call in turn.tool_calls],
                indent=2,
                ensure_ascii=False,
            ),
        ), label="turn-parsed-calls")
        await write_turn_checkpoint_and_publish_if_needed(
            executor=executor,
            control_plane=control_plane,
            destination=destination,
            turn=turn,
            context=context,
            prompt_hash=prompt_hash,
        )

        if turn.tool_calls:
            turn = await control_plane.dispatcher.execute_tools(
                turn=turn,
                control_plane=control_plane,
                destination=destination, memory_inputs=memory_inputs, memory_events=memory_events,
                toolbox=toolbox,
                context=context,
                issue=issue,
                on_turn_captured=adopt_dispatch_turn,
            )
            current_turn = turn
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
                destination.workspace,
            )

        await verify_turn_completion_claims(toolbox=toolbox, turn=turn, context=context)
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
                "extraction_strategy": str((turn.raw or {}).get("extraction_strategy") or ""),
                "execution_profile": context.get("execution_profile"),
                "builder_seat_choice": context.get("builder_seat_choice"),
                "reviewer_seat_choice": context.get("reviewer_seat_choice"),
                "seat_coercion": context.get("seat_coercion"),
                "artifact_contract": context.get("artifact_contract"),
                "odr_active": bool(context.get("odr_active")),
                "odr_valid": context.get("odr_valid"),
                "odr_pending_decisions": context.get("odr_pending_decisions"),
                "odr_stop_reason": context.get("odr_stop_reason"),
                "odr_termination_reason": context.get("odr_termination_reason"),
                "odr_final_auditor_verdict": context.get("odr_final_auditor_verdict"),
                "odr_artifact_path": context.get("odr_artifact_path"),
                "replayed_from_control_plane": bool(
                    (turn.raw or {}).get("control_plane_resume", {}).get("artifact_reused")
                ),
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
            },
            destination.workspace,
        )
        await emit_turn_memory_traces(
            destination=destination, memory_inputs=memory_inputs, memory_events=memory_events,
            context=context, current_turn=turn,
        )
        return TurnResult.succeeded(turn)

    except CardCompletionRejected as exc:
        await emit_failure(str(exc), "completion_rejected")
        return TurnResult.failed(f"Completion rejected: {exc}", should_retry=False)

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
            destination.workspace,
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
            destination.workspace,
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
            destination.workspace,
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
            destination.workspace,
        )
        await emit_failure(str(exc), "control_plane_blocked")
        return TurnResult.failed(str(exc), should_retry=False)

    except ModelTimeoutError as exc:
        executor.middleware.apply_on_turn_failure(exc, issue=issue, role=role, context=context)
        retry_exhausted = bool(context.get("turn_retry_exhausted"))
        log_event(
            "turn_failed",
            {
                "issue_id": issue_id,
                "error": str(exc),
                "type": "turn_retry_exhausted" if retry_exhausted else "timeout",
                "session_id": session_id,
                "turn_index": turn_index,
                "turn_trace_id": turn_trace_id,
            },
            destination.workspace,
        )
        await emit_failure(str(exc), "turn_retry_exhausted" if retry_exhausted else "timeout")
        return TurnResult.failed(str(exc), should_retry=not retry_exhausted)

    except (ModelConnectionError, ModelProviderError) as exc:
        executor.middleware.apply_on_turn_failure(exc, issue=issue, role=role, context=context)
        log_event(
            "turn_failed",
            {
                "issue_id": issue_id,
                "error": str(exc),
                "type": "turn_retry_exhausted",
                "session_id": session_id,
                "turn_index": turn_index,
                "turn_trace_id": turn_trace_id,
            },
            destination.workspace,
        )
        await emit_failure(str(exc), "turn_retry_exhausted")
        return TurnResult.failed(str(exc), should_retry=False)

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
            destination.workspace,
        )
        await emit_failure(str(exc), type(exc).__name__)
        return TurnResult.failed(f"Unexpected error: {exc}", should_retry=False)
