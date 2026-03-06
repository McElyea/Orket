from __future__ import annotations

import inspect
from typing import Any, Dict, Optional


async def invoke_model_complete(model_client: Any, messages: list[dict[str, str]], context: Dict[str, Any]) -> Any:
    complete = getattr(model_client, "complete")
    try:
        parameters = inspect.signature(complete).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "runtime_context" in parameters:
        return await complete(messages, runtime_context=context)
    return await complete(messages)


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
        str(value).strip().lower()
        for value in (context.get("roles") or [context.get("role")])
        if str(value).strip()
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
