from __future__ import annotations

import asyncio
from typing import Any

from orket.runtime.prompt_budget_policy import (
    DEFAULT_PROMPT_BUDGET_PATH,
    load_prompt_budget_policy,
    resolve_prompt_stage,
)
from orket.runtime.protocol_error_codes import (
    E_PROMPT_BUDGET_EXCEEDED_PREFIX,
    E_TOKENIZER_ACCOUNTING_PREFIX,
    format_protocol_error,
)

from .turn_prompt_budget_artifacts import write_prompt_budget_artifacts


async def maybe_record_prompt_budget(
    *,
    workspace: Any,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
    prompt_hash: str,
    messages: list[dict[str, str]],
    context: dict[str, Any],
    model_client: Any,
) -> dict[str, Any] | None:
    prompt_budget_enabled = bool(context.get("prompt_budget_enabled", context.get("protocol_governed_enabled", False)))
    if not prompt_budget_enabled:
        return None

    prompt_budget_result = await evaluate_prompt_budget(
        messages=messages,
        context=context,
        model_client=model_client,
    )
    prompt_structure = build_prompt_structure_payload(
        context=context,
        prompt_hash=prompt_hash,
        message_count=len(messages),
        budget_result=prompt_budget_result,
    )
    await asyncio.to_thread(
        write_prompt_budget_artifacts,
        workspace=workspace,
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index,
        prompt_budget_usage=prompt_budget_result,
        prompt_structure=prompt_structure,
    )
    return prompt_budget_result


async def evaluate_prompt_budget(
    *,
    messages: list[dict[str, str]],
    context: dict[str, Any],
    model_client: Any,
) -> dict[str, Any]:
    policy_path = str(context.get("prompt_budget_policy_path") or str(DEFAULT_PROMPT_BUDGET_PATH)).strip()
    policy = await asyncio.to_thread(load_prompt_budget_policy, policy_path)
    stage = resolve_prompt_stage(context)
    stage_limits = dict(policy["stages"][stage])
    require_backend_tokenizer = bool(context.get("prompt_budget_require_backend_tokenizer", False))

    protocol_messages, tool_schema_messages, task_messages = _partition_prompt_messages(messages)
    token_stats = await _count_prompt_token_buckets(
        model_client=model_client,
        messages=messages,
        protocol_messages=protocol_messages,
        tool_schema_messages=tool_schema_messages,
        task_messages=task_messages,
        require_backend_tokenizer=require_backend_tokenizer,
    )
    if token_stats.get("error"):
        return {
            "ok": False,
            "error": token_stats["error"],
            "stage": stage,
            "budget_policy_version": policy["budget_policy_version"],
            "budget_schema_version": policy["schema_version"],
            "tokenizer_id": str(token_stats.get("tokenizer_id") or ""),
            "tokenizer_source": str(token_stats.get("tokenizer_source") or "unknown"),
            "limits": stage_limits,
            "usage": {},
        }

    usage = {
        "max_tokens": int(token_stats["total_tokens"]),
        "protocol_tokens": int(token_stats["protocol_tokens"]),
        "tool_schema_tokens": int(token_stats["tool_schema_tokens"]),
        "task_tokens": int(token_stats["task_tokens"]),
    }
    for key in ("max_tokens", "protocol_tokens", "tool_schema_tokens", "task_tokens"):
        if int(usage[key]) > int(stage_limits[key]):
            return {
                "ok": False,
                "error": format_protocol_error(
                    E_PROMPT_BUDGET_EXCEEDED_PREFIX,
                    f"{stage}:{key}:{usage[key]}>{stage_limits[key]}",
                ),
                "stage": stage,
                "budget_policy_version": policy["budget_policy_version"],
                "budget_schema_version": policy["schema_version"],
                "tokenizer_id": str(token_stats.get("tokenizer_id") or ""),
                "tokenizer_source": str(token_stats.get("tokenizer_source") or "unknown"),
                "limits": stage_limits,
                "usage": usage,
            }

    return {
        "ok": True,
        "error": "",
        "stage": stage,
        "budget_policy_version": policy["budget_policy_version"],
        "budget_schema_version": policy["schema_version"],
        "tokenizer_id": str(token_stats.get("tokenizer_id") or ""),
        "tokenizer_source": str(token_stats.get("tokenizer_source") or "unknown"),
        "limits": stage_limits,
        "usage": usage,
    }


def build_prompt_structure_payload(
    *,
    context: dict[str, Any],
    prompt_hash: str,
    message_count: int,
    budget_result: dict[str, Any],
) -> dict[str, Any]:
    prompt_metadata = context.get("prompt_metadata")
    prompt_metadata = prompt_metadata if isinstance(prompt_metadata, dict) else {}
    return {
        "schema_version": "1.0",
        "prompt_hash": str(prompt_hash or ""),
        "message_count": int(message_count),
        "prompt_stage": str(budget_result.get("stage") or "executor"),
        "prompt_template_version": str(prompt_metadata.get("prompt_version") or "unknown-v1"),
        "tokenizer_id": str(budget_result.get("tokenizer_id") or ""),
        "tokenizer_source": str(budget_result.get("tokenizer_source") or "unknown"),
        "budget_policy_version": str(budget_result.get("budget_policy_version") or ""),
    }


def _partition_prompt_messages(
    messages: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    protocol_markers = (
        "Turn Success Contract:",
        "Write Path Contract:",
        "Read Path Contract:",
        "Missing Input Preflight Notice:",
        "Architecture Decision Contract:",
        "Guard Rejection Contract:",
    )
    tool_schema_markers = (
        "Execution Context JSON:",
        "Hallucination Verification Scope:",
    )

    protocol_messages: list[dict[str, str]] = []
    tool_schema_messages: list[dict[str, str]] = []
    task_messages: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        content = str(message.get("content") or "")
        if role == "system" or content.startswith(protocol_markers):
            protocol_messages.append(dict(message))
            continue
        if content.startswith(tool_schema_markers):
            tool_schema_messages.append(dict(message))
            continue
        task_messages.append(dict(message))
    return protocol_messages, tool_schema_messages, task_messages


async def _count_prompt_token_buckets(
    *,
    model_client: Any,
    messages: list[dict[str, str]],
    protocol_messages: list[dict[str, str]],
    tool_schema_messages: list[dict[str, str]],
    task_messages: list[dict[str, str]],
    require_backend_tokenizer: bool,
) -> dict[str, Any]:
    total = await _count_tokens(
        model_client=model_client,
        messages=messages,
        require_backend_tokenizer=require_backend_tokenizer,
    )
    if total.get("error"):
        return total
    protocol = await _count_tokens(
        model_client=model_client,
        messages=protocol_messages,
        require_backend_tokenizer=require_backend_tokenizer,
        tokenizer_hint=total.get("tokenizer_id"),
    )
    if protocol.get("error"):
        return protocol
    tool_schema = await _count_tokens(
        model_client=model_client,
        messages=tool_schema_messages,
        require_backend_tokenizer=require_backend_tokenizer,
        tokenizer_hint=total.get("tokenizer_id"),
    )
    if tool_schema.get("error"):
        return tool_schema
    task = await _count_tokens(
        model_client=model_client,
        messages=task_messages,
        require_backend_tokenizer=require_backend_tokenizer,
        tokenizer_hint=total.get("tokenizer_id"),
    )
    if task.get("error"):
        return task
    return {
        "total_tokens": int(total["token_count"]),
        "protocol_tokens": int(protocol["token_count"]),
        "tool_schema_tokens": int(tool_schema["token_count"]),
        "task_tokens": int(task["token_count"]),
        "tokenizer_id": str(total.get("tokenizer_id") or ""),
        "tokenizer_source": str(total.get("tokenizer_source") or "unknown"),
    }


async def _count_tokens(
    *,
    model_client: Any,
    messages: list[dict[str, str]],
    require_backend_tokenizer: bool,
    tokenizer_hint: str | None = None,
) -> dict[str, Any]:
    if not messages:
        return {
            "token_count": 0,
            "tokenizer_id": str(tokenizer_hint or ""),
            "tokenizer_source": "backend" if tokenizer_hint else "empty",
        }

    counter = _resolve_token_counter(model_client)
    if callable(counter):
        try:
            counted = counter(messages)
            if asyncio.iscoroutine(counted):
                counted = await counted
        except (ValueError, TypeError, RuntimeError, OSError, AttributeError) as exc:
            if require_backend_tokenizer:
                return {
                    "error": format_protocol_error(E_TOKENIZER_ACCOUNTING_PREFIX, f"backend_counter_error:{exc}"),
                    "tokenizer_id": "",
                    "tokenizer_source": "backend",
                }
            counted = None
        parsed = _parse_token_counter_payload(counted)
        if parsed is not None:
            token_count, tokenizer_id = parsed
            return {
                "token_count": int(token_count),
                "tokenizer_id": str(tokenizer_id or tokenizer_hint or ""),
                "tokenizer_source": "backend",
            }
        if require_backend_tokenizer:
            return {
                "error": format_protocol_error(E_TOKENIZER_ACCOUNTING_PREFIX, "backend_counter_invalid_payload"),
                "tokenizer_id": "",
                "tokenizer_source": "backend",
            }

    if require_backend_tokenizer:
        return {
            "error": format_protocol_error(E_TOKENIZER_ACCOUNTING_PREFIX, "backend_counter_unavailable"),
            "tokenizer_id": "",
            "tokenizer_source": "backend",
        }

    return {
        "token_count": _deterministic_fallback_token_count(messages),
        "tokenizer_id": str(tokenizer_hint or "deterministic-fallback-v1"),
        "tokenizer_source": "deterministic_fallback",
    }


def _resolve_token_counter(model_client: Any) -> Any:
    counter = getattr(model_client, "count_tokens", None)
    if callable(counter):
        return counter
    provider = getattr(model_client, "provider", None)
    provider_counter = getattr(provider, "count_tokens", None)
    if callable(provider_counter):
        return provider_counter
    return None


def _parse_token_counter_payload(value: Any) -> tuple[int, str] | None:
    if isinstance(value, int) and value >= 0:
        return value, ""
    if not isinstance(value, dict):
        return None
    token_count = value.get("token_count")
    if not isinstance(token_count, int) or token_count < 0:
        token_count = value.get("prompt_tokens")
    if not isinstance(token_count, int) or token_count < 0:
        return None
    tokenizer_id = str(value.get("tokenizer_id") or "")
    return token_count, tokenizer_id


def _deterministic_fallback_token_count(messages: list[dict[str, str]]) -> int:
    total = 0
    for row in messages:
        if not isinstance(row, dict):
            continue
        content = str(row.get("content") or "")
        # Stable fallback approximation when backend tokenizer is unavailable.
        total += max(1, (len(content) + 3) // 4)
    return int(total)
