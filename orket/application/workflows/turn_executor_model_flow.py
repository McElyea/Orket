from __future__ import annotations

import asyncio
import copy
import json
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.application.workflows.turn_executor_model_artifacts import (
    log_turn_start,
    write_response_artifacts,
)
from orket.application.workflows.prompt_budget_guard import maybe_record_prompt_budget
from orket.application.workflows.turn_executor_resume_replay import load_pre_effect_resume_turn_if_needed
from orket.application.workflows.turn_executor_runtime import (
    invoke_model_complete as _invoke_model_complete,
    synthesize_required_status_tool_call,
)
from orket.domain.execution import ExecutionTurn
from orket.logging import log_event
from orket.schema import IssueConfig, RoleConfig

if TYPE_CHECKING:
    from .turn_executor import TurnExecutor


FailureEmitter = Callable[[str, str, ExecutionTurn | None], Awaitable[None]]
FailedResultFactory = Callable[[str, bool], Any]


async def prepare_turn_for_execution(
    *,
    executor: TurnExecutor,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    context: dict[str, Any],
    system_prompt: str | None,
    session_id: str,
    turn_index: int,
    turn_trace_id: str,
    emit_failure: FailureEmitter,
    turn_result_failed: FailedResultFactory,
) -> tuple[ExecutionTurn | None, str, Any | None]:
    turn = await load_pre_effect_resume_turn_if_needed(
        executor=executor,
        issue_id=issue.id,
        role_name=role.name,
        context=context,
    )
    if turn is not None:
        prompt_hash = str((turn.raw or {}).get("prompt_hash") or "").strip()
        if not prompt_hash:
            raise TurnToolControlPlaneError(
                "resumed governed turn is missing checkpoint prompt_hash for replayed checkpoint publication"
            )
        return turn, prompt_hash, None
    return await _generate_turn_via_model(
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
        turn_result_failed=turn_result_failed,
    )


async def _generate_turn_via_model(
    *,
    executor: TurnExecutor,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    context: dict[str, Any],
    system_prompt: str | None,
    session_id: str,
    turn_index: int,
    turn_trace_id: str,
    emit_failure: FailureEmitter,
    turn_result_failed: FailedResultFactory,
) -> tuple[ExecutionTurn | None, str, Any | None]:
    messages = await executor.message_builder.prepare_messages(
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

    executor.artifact_writer.append_memory_event(
        context,
        role_name=role.name,
        interceptor="before_prompt",
        decision_type="prompt_ready",
    )
    prompt_hash, early_result = await _prepare_prompt_and_write_artifacts(
        executor=executor,
        issue=issue,
        role=role,
        model_client=model_client,
        context=context,
        messages=messages,
        session_id=session_id,
        turn_index=turn_index,
        turn_trace_id=turn_trace_id,
        emit_failure=emit_failure,
        turn_result_failed=turn_result_failed,
    )
    if early_result is not None:
        return None, "", early_result

    turn, early_result = await _invoke_and_parse_turn(
        executor=executor,
        issue=issue,
        role=role,
        model_client=model_client,
        context=context,
        session_id=session_id,
        turn_index=turn_index,
        messages=messages,
        emit_failure=emit_failure,
        turn_result_failed=turn_result_failed,
    )
    if early_result is not None or turn is None:
        return None, "", early_result

    contract_violations = executor.contract_validator.collect_contract_violations(turn, role, context)
    if not contract_violations:
        return turn, prompt_hash, None

    return await _retry_after_contract_violations(
        executor=executor,
        issue=issue,
        role=role,
        model_client=model_client,
        context=context,
        session_id=session_id,
        turn_index=turn_index,
        turn_trace_id=turn_trace_id,
        messages=messages,
        initial_turn=turn,
        contract_violations=contract_violations,
        prompt_hash=prompt_hash,
        emit_failure=emit_failure,
        turn_result_failed=turn_result_failed,
    )


async def _prepare_prompt_and_write_artifacts(
    *,
    executor: TurnExecutor,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    context: dict[str, Any],
    messages: list[dict[str, str]],
    session_id: str,
    turn_index: int,
    turn_trace_id: str,
    emit_failure: FailureEmitter,
    turn_result_failed: FailedResultFactory,
) -> tuple[str, Any | None]:
    prompt_hash = executor.artifact_writer.message_hash(messages)
    prompt_budget_result = await maybe_record_prompt_budget(
        workspace=executor.workspace,
        session_id=session_id,
        issue_id=issue.id,
        role_name=role.name,
        turn_index=turn_index,
        prompt_hash=prompt_hash,
        messages=messages,
        context=context,
        model_client=model_client,
    )
    if isinstance(prompt_budget_result, dict) and not bool(prompt_budget_result.get("ok", False)):
        budget_error = str(prompt_budget_result.get("error") or "E_PROMPT_BUDGET_EXCEEDED")
        log_event(
            "turn_failed",
            {
                "issue_id": issue.id,
                "role": role.name,
                "session_id": session_id,
                "turn_index": turn_index,
                "turn_trace_id": turn_trace_id,
                "type": "prompt_budget_exceeded",
                "error": budget_error,
                "prompt_budget_usage": prompt_budget_result,
            },
            executor.workspace,
        )
        await emit_failure(budget_error, "prompt_budget_exceeded", None)
        return "", turn_result_failed(budget_error, False)
    log_turn_start(
        executor=executor,
        issue=issue,
        role=role,
        context=context,
        session_id=session_id,
        turn_index=turn_index,
        turn_trace_id=turn_trace_id,
        prompt_hash=prompt_hash,
        messages=messages,
        prompt_budget_result=prompt_budget_result,
    )
    await asyncio.to_thread(
        executor.artifact_writer.write_turn_artifact,
        session_id=session_id,
        issue_id=issue.id,
        role_name=role.name,
        turn_index=turn_index,
        filename="messages.json",
        content=json.dumps(messages, indent=2, ensure_ascii=False),
    )
    await asyncio.to_thread(
        executor.artifact_writer.write_turn_artifact,
        session_id=session_id,
        issue_id=issue.id,
        role_name=role.name,
        turn_index=turn_index,
        filename="prompt_layers.json",
        content=json.dumps(context.get("prompt_layers", {}), indent=2, ensure_ascii=False, default=str),
    )
    return prompt_hash, None


async def _invoke_and_parse_turn(
    *,
    executor: TurnExecutor,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    context: dict[str, Any],
    session_id: str,
    turn_index: int,
    messages: list[dict[str, str]],
    emit_failure: FailureEmitter,
    turn_result_failed: FailedResultFactory,
) -> tuple[ExecutionTurn | None, Any | None]:
    response = await _invoke_model_complete(model_client, messages, context)
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

    executor.artifact_writer.append_memory_event(
        context,
        role_name=role.name,
        interceptor="after_model",
        decision_type="model_response_processed",
    )
    await write_response_artifacts(
        executor,
        session_id=session_id,
        issue_id=issue.id,
        role_name=role.name,
        turn_index=turn_index,
        response=response,
    )
    turn = executor.response_parser.parse_response(
        response=response,
        issue_id=issue.id,
        role_name=role.name,
        context=context,
    )
    synthesize_required_status_tool_call(turn, context)
    return turn, None


async def _retry_after_contract_violations(
    *,
    executor: TurnExecutor,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    context: dict[str, Any],
    session_id: str,
    turn_index: int,
    turn_trace_id: str,
    messages: list[dict[str, str]],
    initial_turn: ExecutionTurn,
    contract_violations: list[dict[str, Any]],
    prompt_hash: str,
    emit_failure: FailureEmitter,
    turn_result_failed: FailedResultFactory,
) -> tuple[ExecutionTurn | None, str, Any | None]:
    corrective_prompt = executor.corrective_prompt_builder.build_corrective_instruction(contract_violations, context)
    rule_fix_hints = executor.corrective_prompt_builder.rule_specific_fix_hints(contract_violations)
    retry_messages = copy.deepcopy(messages)
    retry_messages.append({"role": "user", "content": corrective_prompt})

    contract_reasons = _contract_reasons(contract_violations)
    log_event(
        "turn_corrective_reprompt",
        {
            "issue_id": issue.id,
            "role": role.name,
            "session_id": session_id,
            "turn_index": turn_index,
            "turn_trace_id": turn_trace_id,
            "reason": contract_reasons[0] if len(contract_reasons) == 1 else "multiple_contracts_not_met",
            "contract_reasons": contract_reasons,
            "contract_violations": contract_violations,
            "rule_fix_hints": rule_fix_hints,
        },
        executor.workspace,
    )

    retry_turn, early_result = await _invoke_and_parse_turn(
        executor=executor,
        issue=issue,
        role=role,
        model_client=model_client,
        context=context,
        session_id=session_id,
        turn_index=turn_index,
        messages=retry_messages,
        emit_failure=emit_failure,
        turn_result_failed=turn_result_failed,
    )
    if early_result is not None or retry_turn is None:
        return None, "", early_result

    remaining_violations = executor.contract_validator.collect_contract_violations(retry_turn, role, context)
    if not remaining_violations:
        return retry_turn, prompt_hash, None

    contract_reasons = _contract_reasons(remaining_violations)
    primary_reason = contract_reasons[0] if contract_reasons else "contract_not_met"
    log_event(
        "turn_non_progress",
        {
            "issue_id": issue.id,
            "role": role.name,
            "session_id": session_id,
            "turn_index": turn_index,
            "turn_trace_id": turn_trace_id,
            "reason": f"{primary_reason}_after_reprompt",
            "contract_reasons": contract_reasons,
            "contract_violations": remaining_violations,
        },
        executor.workspace,
    )
    await emit_failure(primary_reason, "contract_violation", retry_turn)
    return None, "", turn_result_failed(
        executor.corrective_prompt_builder.deterministic_failure_message(primary_reason),
        False,
    )


def _contract_reasons(contract_violations: list[dict[str, Any]]) -> list[str]:
    return [
        str(item.get("reason", "")).strip()
        for item in contract_violations
        if str(item.get("reason", "")).strip()
    ]


__all__ = ["prepare_turn_for_execution"]
