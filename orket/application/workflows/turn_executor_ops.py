from __future__ import annotations

import copy
import json
import time
from typing import Any, Dict, Optional

from orket.logging import log_event
from orket.core.domain.state_machine import StateMachineError
from orket.schema import IssueConfig, RoleConfig


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

    def emit_failure_traces(error: str, failure_type: str) -> None:
        executor._append_memory_event(
            context,
            role_name=role_name,
            interceptor="on_turn_failure",
            decision_type=str(failure_type).strip() or "turn_failed",
        )
        executor._emit_memory_traces(
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

    try:
        if executor._memory_trace_enabled(context):
            context["_memory_trace_events"] = []
        executor._validate_preconditions(issue, role, context)

        messages = await executor._prepare_messages(issue, role, context, system_prompt)
        messages, middleware_outcome = executor.middleware.apply_before_prompt(
            messages,
            issue=issue,
            role=role,
            context=context,
        )
        if middleware_outcome and middleware_outcome.short_circuit:
            reason = middleware_outcome.reason or "short-circuit before_prompt"
            emit_failure_traces(reason, "before_prompt_short_circuit")
            return TurnResult.failed(reason, should_retry=False)
        executor._append_memory_event(
            context,
            role_name=role_name,
            interceptor="before_prompt",
            decision_type="prompt_ready",
        )
        prompt_hash = executor._message_hash(messages)

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
            },
            executor.workspace,
        )
        executor._write_turn_artifact(
            session_id,
            issue_id,
            role_name,
            turn_index,
            "messages.json",
            json.dumps(messages, indent=2, ensure_ascii=False),
        )
        executor._write_turn_artifact(
            session_id,
            issue_id,
            role_name,
            turn_index,
            "prompt_layers.json",
            json.dumps(context.get("prompt_layers", {}), indent=2, ensure_ascii=False, default=str),
        )

        response = await model_client.complete(messages)
        response, middleware_outcome = executor.middleware.apply_after_model(
            response,
            issue=issue,
            role=role,
            context=context,
        )
        if middleware_outcome and middleware_outcome.short_circuit:
            reason = middleware_outcome.reason or "short-circuit after_model"
            emit_failure_traces(reason, "after_model_short_circuit")
            return TurnResult.failed(reason, should_retry=False)
        executor._append_memory_event(
            context,
            role_name=role_name,
            interceptor="after_model",
            decision_type="model_response_processed",
        )
        response_content = getattr(response, "content", "") if not isinstance(response, dict) else response.get("content", "")
        response_raw = getattr(response, "raw", {}) if not isinstance(response, dict) else response
        executor._write_turn_artifact(session_id, issue_id, role_name, turn_index, "model_response.txt", response_content or "")
        executor._write_turn_artifact(
            session_id,
            issue_id,
            role_name,
            turn_index,
            "model_response_raw.json",
            json.dumps(response_raw, indent=2, ensure_ascii=False, default=str),
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
            response = await model_client.complete(retry_messages)
            response, middleware_outcome = executor.middleware.apply_after_model(
                response,
                issue=issue,
                role=role,
                context=context,
            )
            if middleware_outcome and middleware_outcome.short_circuit:
                reason = middleware_outcome.reason or "short-circuit after_model"
                emit_failure_traces(reason, "after_model_short_circuit")
                return TurnResult.failed(reason, should_retry=False)
            executor._append_memory_event(
                context,
                role_name=role_name,
                interceptor="after_model",
                decision_type="model_response_reprompt_processed",
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
                emit_failure_traces(primary_reason, "contract_violation")
                return TurnResult.failed(executor._deterministic_failure_message(primary_reason), should_retry=False)

        executor._write_turn_artifact(
            session_id,
            issue_id,
            role_name,
            turn_index,
            "parsed_tool_calls.json",
            json.dumps([{"tool": tool_call.tool, "args": tool_call.args} for tool_call in turn.tool_calls], indent=2, ensure_ascii=False),
        )
        executor._write_turn_checkpoint(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            prompt_hash=prompt_hash,
            selected_model=context.get("selected_model"),
            tool_calls=[{"tool": tool_call.tool, "args": tool_call.args} for tool_call in turn.tool_calls],
            state_delta=executor._state_delta_from_tool_calls(context, turn),
            prompt_metadata=context.get("prompt_metadata"),
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
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
            },
            executor.workspace,
        )
        executor._emit_memory_traces(
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
        emit_failure_traces(str(exc), "state_violation")
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
        emit_failure_traces(str(exc), "tool_violation")
        return TurnResult.governance_violation(exc.violations)

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
        emit_failure_traces(str(exc), "timeout")
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
        emit_failure_traces(str(exc), type(exc).__name__)
        return TurnResult.failed(f"Unexpected error: {exc}", should_retry=False)


def runtime_tokens_payload(turn: Any) -> Any:
    raw_data = turn.raw if isinstance(turn.raw, dict) else {}
    usage = raw_data.get("usage") if isinstance(raw_data.get("usage"), dict) else {}
    timings = raw_data.get("timings") if isinstance(raw_data.get("timings"), dict) else {}

    prompt_tokens = usage.get("prompt_tokens", raw_data.get("input_tokens"))
    output_tokens = usage.get("completion_tokens", raw_data.get("output_tokens"))
    total_tokens = usage.get("total_tokens", raw_data.get("total_tokens", turn.tokens_used))

    prompt_ms = timings.get("prompt_ms")
    predicted_ms = timings.get("predicted_ms")

    has_tokens = isinstance(prompt_tokens, int) and isinstance(output_tokens, int)
    has_timings = isinstance(prompt_ms, (int, float)) and isinstance(predicted_ms, (int, float))

    status = "OK"
    if not has_tokens and not has_timings:
        status = "TOKEN_AND_TIMING_UNAVAILABLE"
    elif not has_tokens:
        status = "TOKEN_COUNT_UNAVAILABLE"
    elif not has_timings:
        status = "TIMING_UNAVAILABLE"

    if not isinstance(total_tokens, int):
        total_tokens = turn.tokens_used if isinstance(turn.tokens_used, int) else None

    return {
        "status": status,
        "prompt_tokens": prompt_tokens if isinstance(prompt_tokens, int) else None,
        "output_tokens": output_tokens if isinstance(output_tokens, int) else None,
        "total_tokens": total_tokens,
        "prompt_ms": float(prompt_ms) if isinstance(prompt_ms, (int, float)) else None,
        "predicted_ms": float(predicted_ms) if isinstance(predicted_ms, (int, float)) else None,
    }


def state_delta_from_tool_calls(context: Dict[str, Any], turn: Any) -> Dict[str, Any]:
    current = context.get("current_status")
    requested = None
    for call in turn.tool_calls:
        if call.tool == "update_issue_status":
            requested = call.args.get("status")
            break
    return {"from": current, "to": requested}


def synthesize_required_status_tool_call(turn: Any, context: Dict[str, Any]) -> None:
    from orket.domain.execution import ToolCall

    role_names = {
        str(value).strip().lower() for value in (context.get("roles") or [context.get("role")]) if str(value).strip()
    }
    required_tools = {
        str(tool).strip() for tool in (context.get("required_action_tools") or []) if str(tool).strip()
    }
    if "update_issue_status" not in required_tools:
        return
    if any(str(call.tool or "").strip() == "update_issue_status" for call in (turn.tool_calls or [])):
        return

    required_statuses = [
        str(status).strip().lower()
        for status in (context.get("required_statuses") or [])
        if str(status).strip()
    ]
    required_status: Optional[str] = None
    if len(required_statuses) == 1:
        required_status = required_statuses[0]
    elif (
        "integrity_guard" in role_names
        and {"done", "blocked"}.issubset(set(required_statuses))
        and bool(context.get("runtime_verifier_ok")) is True
    ):
        required_status = "done"
    if not required_status or required_status == "blocked":
        return

    turn.tool_calls.append(
        ToolCall(
            tool="update_issue_status",
            args={"status": required_status},
            result=None,
            error=None,
        )
    )
