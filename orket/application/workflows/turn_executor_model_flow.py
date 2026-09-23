from __future__ import annotations

import asyncio
import copy
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.application.workflows import turn_executor_partial_parse as partial_parse
from orket.application.workflows.turn_executor_model_artifacts import write_response_artifacts
from orket.application.workflows.turn_executor_resume_replay import load_pre_effect_resume_turn_if_needed
from orket.application.workflows.turn_executor_runtime import invoke_model_complete as _invoke_model_complete
from orket.application.workflows.turn_executor_runtime import synthesize_required_status_tool_call
from orket.core.domain.execution import ExecutionTurn
from orket.exceptions import ModelProviderError
from orket.logging import log_event
from orket.schema import IssueConfig, RoleConfig

from .turn_artifact_destination import TurnArtifactDestination
from .turn_contract_input_capture import (
    ValidationAttemptInputs,
    collect_validation_attempt,
    contract_reasons,
    required_read_observation_for_correction,
)
from .turn_control_plane_binding import TurnControlPlaneBinding
from .turn_memory_trace_artifacts import append_memory_event
from .turn_prompt_publication import prepare_prompt_and_write_artifacts
from .turn_response_capture import capture_turn_response

if TYPE_CHECKING:
    from .turn_executor import TurnExecutor, TurnResult


FailureEmitter = Callable[[str, str, ExecutionTurn | None], Awaitable[None]]
FailedResultFactory = Callable[[str, bool], "TurnResult"]


async def prepare_turn_for_execution(
    *,
    executor: TurnExecutor,
    control_plane: TurnControlPlaneBinding,
    destination: TurnArtifactDestination,
    memory_events: list[dict[str, Any]] | None,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    context: dict[str, Any],
    system_prompt: str | None,
    turn_trace_id: str,
    emit_failure: FailureEmitter,
    turn_result_failed: FailedResultFactory,
) -> tuple[ExecutionTurn | None, str, TurnResult | None]:
    turn = await load_pre_effect_resume_turn_if_needed(
        control_plane=control_plane, destination=destination,
    )
    if turn is not None:
        prompt_hash = str((turn.raw or {}).get("prompt_hash") or "").strip()
        if not prompt_hash:
            raise TurnToolControlPlaneError(
                "resumed governed turn is missing checkpoint prompt_hash for replayed checkpoint publication"
            )
        return turn, prompt_hash, None
    return await _generate_turn_via_model(
        executor=executor, destination=destination, memory_events=memory_events,
        issue=issue,
        role=role,
        model_client=model_client,
        context=context,
        system_prompt=system_prompt,
        turn_trace_id=turn_trace_id,
        emit_failure=emit_failure,
        turn_result_failed=turn_result_failed,
    )


async def _generate_turn_via_model(
    *,
    executor: TurnExecutor,
    destination: TurnArtifactDestination,
    memory_events: list[dict[str, Any]] | None,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    context: dict[str, Any],
    system_prompt: str | None,
    turn_trace_id: str,
    emit_failure: FailureEmitter,
    turn_result_failed: FailedResultFactory,
) -> tuple[ExecutionTurn | None, str, TurnResult | None]:
    role_name = destination.role_name
    messages = await executor.message_builder.prepare_messages(
        destination=destination,
        issue=issue,
        role=role,
        context=context,
        system_prompt=system_prompt,
    )
    messages, middleware_outcome = executor.middleware.apply_before_prompt(
        messages,
        issue=issue,
        role=role,
        context=context,
    )
    if middleware_outcome and middleware_outcome.short_circuit:
        reason = middleware_outcome.reason or "short-circuit before_prompt"
        await emit_failure(reason, "before_prompt_short_circuit", None)
        return None, "", turn_result_failed(reason, False)

    append_memory_event(
        memory_events,
        role_name=role_name,
        interceptor="before_prompt",
        decision_type="prompt_ready",
    )
    messages, prompt_hash, early_result = await prepare_prompt_and_write_artifacts(
        destination=destination,
        model_client=model_client,
        context=context,
        messages=messages,
        turn_trace_id=turn_trace_id,
        emit_failure=emit_failure,
        turn_result_failed=turn_result_failed,
    )
    if early_result is not None:
        return None, "", early_result

    turn, early_result = await _invoke_and_parse_turn(
        executor=executor, destination=destination, memory_events=memory_events,
        issue=issue,
        role=role,
        model_client=model_client,
        context=context,
        messages=messages,
        emit_failure=emit_failure,
        turn_result_failed=turn_result_failed,
    )
    if early_result is not None or turn is None:
        return None, "", early_result

    if turn.partial_parse_failure and partial_parse.partial_parse_recovery_policy(context) != "retry":
        return await partial_parse.blocked_partial_parse_failure(
            destination=destination,
            context=context,
            turn_trace_id=turn_trace_id,
            turn=turn,
            emit_failure=emit_failure,
            turn_result_failed=turn_result_failed,
        )

    attempt, contract_violations = await collect_validation_attempt(
        validator=executor.contract_validator, turn=turn, role=role,
        context=context, workspace=destination.workspace,
    )
    if not contract_violations:
        return attempt.turn, prompt_hash, None

    return await _retry_after_contract_violations(
        executor=executor, destination=destination, memory_events=memory_events,
        issue=issue,
        role=role,
        model_client=model_client,
        context=context,
        turn_trace_id=turn_trace_id,
        messages=messages,
        contract_violations=contract_violations,
        validation_attempt=attempt,
        prompt_hash=prompt_hash,
        emit_failure=emit_failure,
        turn_result_failed=turn_result_failed,
    )


async def _invoke_and_parse_turn(
    *,
    executor: TurnExecutor,
    destination: TurnArtifactDestination,
    memory_events: list[dict[str, Any]] | None,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    context: dict[str, Any],
    messages: list[dict[str, str]],
    emit_failure: FailureEmitter,
    turn_result_failed: FailedResultFactory,
) -> tuple[ExecutionTurn | None, TurnResult | None]:
    role_name = destination.role_name
    response = await _invoke_model_complete_with_retries(
        executor=executor, destination=destination, memory_events=memory_events,
        issue=issue,
        role=role,
        model_client=model_client,
        messages=messages,
        context=context,
    )
    response, middleware_outcome = executor.middleware.apply_after_model(
        response,
        issue=issue,
        role=role,
        context=context,
    )
    if middleware_outcome and middleware_outcome.short_circuit:
        reason = middleware_outcome.reason or "short-circuit after_model"
        await emit_failure(reason, "after_model_short_circuit", None)
        return None, turn_result_failed(reason, False)

    append_memory_event(
        memory_events,
        role_name=role_name,
        interceptor="after_model",
        decision_type="model_response_processed",
    )
    captured_response = capture_turn_response(response)
    await write_response_artifacts(destination=destination, response=captured_response)
    turn = await executor.response_parser.parse_response(
        response=captured_response, destination=destination, context=context,
    )
    synthesize_required_status_tool_call(turn, context)
    return turn, None


async def _retry_after_contract_violations(
    *,
    executor: TurnExecutor,
    destination: TurnArtifactDestination,
    memory_events: list[dict[str, Any]] | None,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    context: dict[str, Any],
    turn_trace_id: str,
    messages: list[dict[str, str]],
    contract_violations: list[dict[str, Any]],
    validation_attempt: ValidationAttemptInputs,
    prompt_hash: str,
    emit_failure: FailureEmitter,
    turn_result_failed: FailedResultFactory,
) -> tuple[ExecutionTurn | None, str, TurnResult | None]:
    required_read_observation = await required_read_observation_for_correction(attempt=validation_attempt)
    corrective_prompt = executor.corrective_prompt_builder.build_corrective_instruction(
        contract_violations,
        validation_attempt.context,
        required_read_observation,
    )
    rule_fix_hints = executor.corrective_prompt_builder.rule_specific_fix_hints(contract_violations)
    retry_messages = copy.deepcopy(messages)
    retry_messages.append({"role": "user", "content": corrective_prompt})

    reasons = contract_reasons(contract_violations)
    log_event(
        "turn_corrective_reprompt",
        {
            "issue_id": destination.issue_id,
            "role": destination.role_name,
            "session_id": destination.session_id,
            "turn_index": destination.turn_index,
            "turn_trace_id": turn_trace_id,
            "reason": reasons[0] if len(reasons) == 1 else "multiple_contracts_not_met",
            "contract_reasons": reasons,
            "contract_violations": contract_violations,
            "rule_fix_hints": rule_fix_hints,
        },
        validation_attempt.workspace,
    )

    retry_turn, early_result = await _invoke_and_parse_turn(
        executor=executor, destination=destination, memory_events=memory_events,
        issue=issue,
        role=role,
        model_client=model_client,
        context=context,
        messages=retry_messages,
        emit_failure=emit_failure,
        turn_result_failed=turn_result_failed,
    )
    if early_result is not None or retry_turn is None:
        return None, "", early_result

    retry_attempt, remaining_violations = await collect_validation_attempt(
        validator=executor.contract_validator, turn=retry_turn, role=role,
        context=context, workspace=validation_attempt.workspace,
    )
    if not remaining_violations:
        return retry_attempt.turn, prompt_hash, None

    reasons = contract_reasons(remaining_violations)
    primary_reason = reasons[0] if reasons else "contract_not_met"
    log_event(
        "turn_non_progress",
        {
            "issue_id": destination.issue_id,
            "role": destination.role_name,
            "session_id": destination.session_id,
            "turn_index": destination.turn_index,
            "turn_trace_id": turn_trace_id,
            "reason": f"{primary_reason}_after_reprompt",
            "contract_reasons": reasons,
            "contract_violations": remaining_violations,
        },
        validation_attempt.workspace,
    )
    await emit_failure(primary_reason, "contract_violation", retry_attempt.turn)
    return None, "", turn_result_failed(
        executor.corrective_prompt_builder.deterministic_failure_message(primary_reason),
        False,
    )


async def _invoke_model_complete_with_retries(
    *,
    executor: TurnExecutor,
    destination: TurnArtifactDestination,
    memory_events: list[dict[str, Any]] | None,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    messages: list[dict[str, str]],
    context: dict[str, Any],
) -> Any:
    try:
        max_retries = max(0, int(context.get("max_turn_retries", context.get("max_retries", 2))))
    except (TypeError, ValueError):
        max_retries = 2
    try:
        base_backoff = max(0.0, float(context.get("turn_retry_backoff_seconds", 1.0)))
    except (TypeError, ValueError):
        base_backoff = 1.0

    for attempt in range(max_retries + 1):
        try:
            return await _invoke_model_complete(model_client, messages, context)
        except ModelProviderError as exc:
            if attempt >= max_retries:
                context["turn_retry_exhausted"] = True
                log_event(
                    "turn_retry_exhausted",
                    {
                        "issue_id": destination.issue_id,
                        "role": destination.role_name,
                        "session_id": destination.session_id,
                        "turn_index": destination.turn_index,
                        "retry_count": attempt,
                        "max_retries": max_retries,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "result": "blocked",
                    },
                    destination.workspace,
                )
                raise
            delay = base_backoff * (2 ** attempt)
            log_event(
                "turn_retry_scheduled",
                {
                    "issue_id": destination.issue_id,
                    "role": destination.role_name,
                    "session_id": destination.session_id,
                    "turn_index": destination.turn_index,
                    "retry_count": attempt + 1,
                    "max_retries": max_retries,
                    "backoff_seconds": delay,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                destination.workspace,
            )
            if delay > 0:
                await asyncio.sleep(delay)
    raise RuntimeError("unreachable model retry state")


__all__ = ["prepare_turn_for_execution"]
