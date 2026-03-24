from __future__ import annotations

import asyncio
import copy
import json
import time
from typing import Any, Dict, Optional

from orket.logging import log_event
from orket.application.services.turn_tool_control_plane_recovery import TurnToolCheckpointRecoveryError
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.core.domain.state_machine import StateMachineError
from orket.schema import IssueConfig, RoleConfig
from .prompt_budget_guard import maybe_record_prompt_budget
from .turn_executor_control_plane import (
    ensure_turn_control_plane_reentry_allowed_if_needed,
    load_completed_turn_replay_if_needed,
    write_turn_checkpoint_and_publish_if_needed,
)
from .turn_failure_traces import emit_turn_failure_traces
from .turn_executor_runtime import (
    invoke_model_complete as _invoke_model_complete,
    runtime_tokens_payload as _runtime_tokens_payload,
    state_delta_from_tool_calls as _state_delta_from_tool_calls,
    synthesize_required_status_tool_call as _synthesize_required_status_tool_call,
)

runtime_tokens_payload = _runtime_tokens_payload
state_delta_from_tool_calls = _state_delta_from_tool_calls
synthesize_required_status_tool_call = _synthesize_required_status_tool_call


def _response_artifact_payload(response: Any) -> tuple[str, Any]:
    response_content = (
        getattr(response, "content", "") if not isinstance(response, dict) else response.get("content", "")
    )
    response_raw = getattr(response, "raw", {}) if not isinstance(response, dict) else response
    return response_content or "", response_raw


async def _write_response_artifacts(
    executor: Any,
    *,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
    response: Any,
) -> None:
    response_content, response_raw = _response_artifact_payload(response)
    await asyncio.to_thread(
        executor._write_turn_artifact,
        session_id,
        issue_id,
        role_name,
        turn_index,
        "model_response.txt",
        response_content,
    )
    await asyncio.to_thread(
        executor._write_turn_artifact,
        session_id,
        issue_id,
        role_name,
        turn_index,
        "model_response_raw.json",
        json.dumps(response_raw, indent=2, ensure_ascii=False, default=str),
    )


async def execute_turn(
    executor: Any,
    issue: IssueConfig,
    role: RoleConfig,
    model_client: Any,
    toolbox: Any,
    context: Dict[str, Any],
    system_prompt: Optional[str] = None,
):
    from .turn_executor import ModelTimeoutError, ToolValidationError, TurnResult

    issue_id = issue.id
    role_name = role.name
    session_id = context.get("session_id", "unknown-session")
    turn_index = int(context.get("turn_index", 0))
    turn_trace_id = f"{session_id}:{issue_id}:{role_name}:{turn_index}"
    started_at = time.perf_counter()
    current_turn = None

    async def emit_failure(error: str, failure_type: str) -> None:
        await emit_turn_failure_traces(
            executor=executor,
            context=context,
            role_name=role_name,
            session_id=session_id,
            issue_id=issue_id,
            turn_index=turn_index,
            issue=issue,
            role=role,
            current_turn=current_turn,
            error=error,
            failure_type=failure_type,
        )

    try:
        if executor._memory_trace_enabled(context):
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
                    "tokens": executor._runtime_tokens_payload(completed_replay_turn),
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "turn_trace_id": turn_trace_id,
                    "replayed_from_control_plane": True,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                },
                executor.workspace,
            )
            await asyncio.to_thread(
                executor._emit_memory_traces,
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

        messages = await executor._prepare_messages(issue, role, context, system_prompt)
        messages, middleware_outcome = executor.middleware.apply_before_prompt(
            messages,
            issue=issue,
            role=role,
            context=context,
        )
        if middleware_outcome and middleware_outcome.short_circuit:
            reason = middleware_outcome.reason or "short-circuit before_prompt"
            await emit_failure(reason, "before_prompt_short_circuit")
            return TurnResult.failed(reason, should_retry=False)
        executor._append_memory_event(
            context,
            role_name=role_name,
            interceptor="before_prompt",
            decision_type="prompt_ready",
        )
        prompt_hash = executor._message_hash(messages)
        prompt_budget_result = await maybe_record_prompt_budget(
            workspace=executor.workspace,
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
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
                    "issue_id": issue_id,
                    "role": role_name,
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "turn_trace_id": turn_trace_id,
                    "type": "prompt_budget_exceeded",
                    "error": budget_error,
                    "prompt_budget_usage": prompt_budget_result,
                },
                executor.workspace,
            )
            await emit_failure(budget_error, "prompt_budget_exceeded")
            return TurnResult.failed(budget_error, should_retry=False)

        log_event(
            "turn_start",
            {
                "issue_id": issue_id,
                "role": role_name,
                "session_id": session_id,
                "turn_index": turn_index,
                "turn_trace_id": turn_trace_id,
                "prompt_hash": prompt_hash,
                "message_count": len(messages),
                "selected_model": context.get("selected_model"),
                "prompt_id": (context.get("prompt_metadata") or {}).get("prompt_id"),
                "prompt_version": (context.get("prompt_metadata") or {}).get("prompt_version"),
                "prompt_checksum": (context.get("prompt_metadata") or {}).get("prompt_checksum"),
                "resolver_policy": (context.get("prompt_metadata") or {}).get("resolver_policy"),
                "selection_policy": (context.get("prompt_metadata") or {}).get("selection_policy"),
                "role_status": (context.get("prompt_metadata") or {}).get("role_status"),
                "dialect_status": (context.get("prompt_metadata") or {}).get("dialect_status"),
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
                "prompt_budget_stage": (prompt_budget_result or {}).get("stage"),
                "prompt_budget_tokenizer_id": (prompt_budget_result or {}).get("tokenizer_id"),
            },
            executor.workspace,
        )
        await asyncio.to_thread(
            executor._write_turn_artifact,
            session_id,
            issue_id,
            role_name,
            turn_index,
            "messages.json",
            json.dumps(messages, indent=2, ensure_ascii=False),
        )
        await asyncio.to_thread(
            executor._write_turn_artifact,
            session_id,
            issue_id,
            role_name,
            turn_index,
            "prompt_layers.json",
            json.dumps(context.get("prompt_layers", {}), indent=2, ensure_ascii=False, default=str),
        )

        response = await _invoke_model_complete(model_client, messages, context)
        response, middleware_outcome = executor.middleware.apply_after_model(
            response,
            issue=issue,
            role=role,
            context=context,
        )
        if middleware_outcome and middleware_outcome.short_circuit:
            reason = middleware_outcome.reason or "short-circuit after_model"
            await emit_failure(reason, "after_model_short_circuit")
            return TurnResult.failed(reason, should_retry=False)
        executor._append_memory_event(
            context,
            role_name=role_name,
            interceptor="after_model",
            decision_type="model_response_processed",
        )
        await _write_response_artifacts(
            executor,
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            response=response,
        )

        turn = executor._parse_response(response=response, issue_id=issue_id, role_name=role_name, context=context)
        current_turn = turn
        executor._synthesize_required_status_tool_call(turn, context)
        contract_violations = executor._collect_contract_violations(turn, role, context)
        if contract_violations:
            corrective_prompt = executor._build_corrective_instruction(contract_violations, context)
            rule_fix_hints = executor._rule_specific_fix_hints(contract_violations)
            retry_messages = copy.deepcopy(messages)
            retry_messages.append({"role": "user", "content": corrective_prompt})

            contract_reasons = [
                str(item.get("reason", "")).strip()
                for item in contract_violations
                if str(item.get("reason", "")).strip()
            ]
            log_event(
                "turn_corrective_reprompt",
                {
                    "issue_id": issue_id,
                    "role": role_name,
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
            response = await _invoke_model_complete(model_client, retry_messages, context)
            response, middleware_outcome = executor.middleware.apply_after_model(
                response,
                issue=issue,
                role=role,
                context=context,
            )
            if middleware_outcome and middleware_outcome.short_circuit:
                reason = middleware_outcome.reason or "short-circuit after_model"
                await emit_failure(reason, "after_model_short_circuit")
                return TurnResult.failed(reason, should_retry=False)
            executor._append_memory_event(
                context,
                role_name=role_name,
                interceptor="after_model",
                decision_type="model_response_reprompt_processed",
            )
            await _write_response_artifacts(
                executor,
                session_id=session_id,
                issue_id=issue_id,
                role_name=role_name,
                turn_index=turn_index,
                response=response,
            )

            turn = executor._parse_response(response=response, issue_id=issue_id, role_name=role_name, context=context)
            current_turn = turn
            executor._synthesize_required_status_tool_call(turn, context)
            contract_violations = executor._collect_contract_violations(turn, role, context)
            if contract_violations:
                contract_reasons = [
                    str(item.get("reason", "")).strip()
                    for item in contract_violations
                    if str(item.get("reason", "")).strip()
                ]
                primary_reason = contract_reasons[0] if contract_reasons else "contract_not_met"
                log_event(
                    "turn_non_progress",
                    {
                        "issue_id": issue_id,
                        "role": role_name,
                        "session_id": session_id,
                        "turn_index": turn_index,
                        "turn_trace_id": turn_trace_id,
                        "reason": f"{primary_reason}_after_reprompt",
                        "contract_reasons": contract_reasons,
                        "contract_violations": contract_violations,
                    },
                    executor.workspace,
                )
                await emit_failure(primary_reason, "contract_violation")
                return TurnResult.failed(executor._deterministic_failure_message(primary_reason), should_retry=False)

        await asyncio.to_thread(
            executor._write_turn_artifact,
            session_id,
            issue_id,
            role_name,
            turn_index,
            "parsed_tool_calls.json",
            json.dumps(
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
            await executor._execute_tools(turn, toolbox, context, issue=issue)
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
                "tokens": executor._runtime_tokens_payload(turn),
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
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
            },
            executor.workspace,
        )
        await asyncio.to_thread(
            executor._emit_memory_traces,
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
