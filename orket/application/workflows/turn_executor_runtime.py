from __future__ import annotations

import inspect
from typing import Any


def _dict_payload(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _supports_runtime_context(callable_obj: Any) -> bool:
    try:
        parameters = inspect.signature(callable_obj).parameters
    except (TypeError, ValueError):
        return False
    return "runtime_context" in parameters


async def invoke_model_complete(model_client: Any, messages: list[dict[str, str]], context: dict[str, Any]) -> Any:
    complete = model_client.complete
    if _supports_runtime_context(complete):
        return await complete(messages, runtime_context=context)

    # Default model-client wrappers can expose provider.complete(runtime_context=...)
    # while their own complete(...) signature does not.
    provider = getattr(model_client, "provider", None)
    provider_complete = getattr(provider, "complete", None)
    if callable(provider_complete) and _supports_runtime_context(provider_complete):
        return await provider_complete(messages, runtime_context=context)

    return await complete(messages)


def runtime_tokens_payload(turn: Any) -> Any:
    raw_data = _dict_payload(turn.raw)
    usage = _dict_payload(raw_data.get("usage"))
    timings = _dict_payload(raw_data.get("timings"))

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


def state_delta_from_tool_calls(context: dict[str, Any], turn: Any) -> dict[str, Any]:
    current = context.get("current_status")
    requested = None
    for call in turn.tool_calls:
        if call.tool == "update_issue_status":
            requested = call.args.get("status")
            break
    return {"from": current, "to": requested}


def synthesize_required_status_tool_call(turn: Any, context: dict[str, Any]) -> None:
    from orket.core.domain.execution import ToolCall

    role_names = {
        str(value).strip().lower() for value in (context.get("roles") or [context.get("role")]) if str(value).strip()
    }
    required_tools = {str(tool).strip() for tool in (context.get("required_action_tools") or []) if str(tool).strip()}
    if "update_issue_status" not in required_tools:
        return
    if any(str(call.tool or "").strip() == "update_issue_status" for call in (turn.tool_calls or [])):
        return

    required_statuses = [
        str(status).strip().lower() for status in (context.get("required_statuses") or []) if str(status).strip()
    ]
    required_status: str | None = None
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
