"""Owned optional prompt-token counter invocation and normalization."""
from __future__ import annotations

import asyncio
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io
from orket.core.contracts.protocol_error_codes import E_TOKENIZER_ACCOUNTING_PREFIX, format_protocol_error

_COUNTER_ERRORS = (ValueError, TypeError, RuntimeError, OSError, AttributeError)


def resolve_token_counter(model_client: Any) -> Any:
    counter = getattr(model_client, "count_tokens", None)
    if callable(counter):
        return counter
    provider = getattr(model_client, "provider", None)
    provider_counter = getattr(provider, "count_tokens", None)
    if callable(provider_counter):
        return provider_counter
    return None


def is_known_async_counter(counter: Any) -> bool:
    counter_call = counter.__call__ if callable(counter) else None
    return bool(
        callable(counter)
        and (asyncio.iscoroutinefunction(counter) or asyncio.iscoroutinefunction(counter_call))
    )


async def count_prompt_token_buckets(
    *, counter: Any, known_async_counter: bool, messages: list[Any],
    protocol_messages: list[dict[str, str]], tool_schema_messages: list[dict[str, str]],
    task_messages: list[dict[str, str]], require_backend_tokenizer: bool,
) -> dict[str, Any]:
    total = await _count_tokens(bucket="total", counter=counter, known_async_counter=known_async_counter,
        messages=messages, require_backend_tokenizer=require_backend_tokenizer)
    if total.get("error"):
        return total
    protocol = await _count_tokens(bucket="protocol", counter=counter, known_async_counter=known_async_counter,
        messages=protocol_messages, require_backend_tokenizer=require_backend_tokenizer,
        tokenizer_hint=total.get("tokenizer_id"))
    if protocol.get("error"):
        return protocol
    tool_schema = await _count_tokens(bucket="tool-schema", counter=counter,
        known_async_counter=known_async_counter, messages=tool_schema_messages,
        require_backend_tokenizer=require_backend_tokenizer, tokenizer_hint=total.get("tokenizer_id"))
    if tool_schema.get("error"):
        return tool_schema
    task = await _count_tokens(bucket="task", counter=counter, known_async_counter=known_async_counter,
        messages=task_messages, require_backend_tokenizer=require_backend_tokenizer,
        tokenizer_hint=total.get("tokenizer_id"))
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
    *, bucket: str, counter: Any, known_async_counter: bool, messages: list[Any],
    require_backend_tokenizer: bool, tokenizer_hint: str | None = None,
) -> dict[str, Any]:
    if not messages:
        return {
            "token_count": 0,
            "tokenizer_id": str(tokenizer_hint or ""),
            "tokenizer_source": "backend" if tokenizer_hint else "empty",
        }
    if callable(counter):
        callback_messages = [dict(row) if isinstance(row, dict) else row for row in messages]
        normalization_messages = [dict(row) if isinstance(row, dict) else row for row in messages]

        async def operation() -> dict[str, Any]:
            try:
                if known_async_counter:
                    counted = await counter(callback_messages)
                else:
                    counted = await asyncio.to_thread(counter, callback_messages)
                    if asyncio.iscoroutine(counted):
                        counted = await counted
            except _COUNTER_ERRORS as exc:
                return _counter_error_result(exc=exc, messages=normalization_messages,
                    require_backend_tokenizer=require_backend_tokenizer, tokenizer_hint=tokenizer_hint)
            return _normalize_counter_result(counted=counted, messages=normalization_messages,
                require_backend_tokenizer=require_backend_tokenizer, tokenizer_hint=tokenizer_hint)

        return await run_owned_io(operation, label=f"prompt-budget-token-counter:{bucket}",
            preserve_failure=True, cancel_on_interrupt=known_async_counter)
    if require_backend_tokenizer:
        return _backend_error("backend_counter_unavailable")
    return _fallback_counter_result(messages=messages, tokenizer_hint=tokenizer_hint)


def _counter_error_result(
    *, exc: BaseException, messages: list[Any], require_backend_tokenizer: bool, tokenizer_hint: str | None,
) -> dict[str, Any]:
    if require_backend_tokenizer:
        return _backend_error(f"backend_counter_error:{exc}")
    return _fallback_counter_result(messages=messages, tokenizer_hint=tokenizer_hint)


def _normalize_counter_result(
    *, counted: Any, messages: list[Any], require_backend_tokenizer: bool, tokenizer_hint: str | None,
) -> dict[str, Any]:
    parsed = _parse_token_counter_payload(counted)
    if parsed is not None:
        token_count, tokenizer_id = parsed
        return {
            "token_count": int(token_count),
            "tokenizer_id": str(tokenizer_id or tokenizer_hint or ""),
            "tokenizer_source": "backend",
        }
    if require_backend_tokenizer:
        return _backend_error("backend_counter_invalid_payload")
    return _fallback_counter_result(messages=messages, tokenizer_hint=tokenizer_hint)


def _backend_error(detail: str) -> dict[str, Any]:
    return {
        "error": format_protocol_error(E_TOKENIZER_ACCOUNTING_PREFIX, detail),
        "tokenizer_id": "",
        "tokenizer_source": "backend",
    }


def _fallback_counter_result(*, messages: list[Any], tokenizer_hint: str | None) -> dict[str, Any]:
    return {
        "token_count": _deterministic_fallback_token_count(messages),
        "tokenizer_id": str(tokenizer_hint or "deterministic-fallback-v1"),
        "tokenizer_source": "deterministic_fallback",
    }


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
    return token_count, str(value.get("tokenizer_id") or "")


def _deterministic_fallback_token_count(messages: list[Any]) -> int:
    total = 0
    for row in messages:
        if not isinstance(row, dict):
            continue
        content = str(row.get("content") or "")
        total += max(1, (len(content) + 3) // 4)
    return int(total)
