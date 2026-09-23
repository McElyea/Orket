from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.core.contracts.protocol_error_codes import (
    E_PROMPT_BUDGET_EXCEEDED_PREFIX,
    format_protocol_error,
)
from orket.runtime.config import contract_assets
from orket.runtime.prompt_budget_policy import load_prompt_budget_policy, resolve_prompt_stage

from .prompt_token_counter import (
    count_prompt_token_buckets,
    is_known_async_counter,
    resolve_token_counter,
)
from .turn_artifact_destination import TurnArtifactDestination
from .turn_prompt_budget_artifacts import write_prompt_budget_artifacts


@dataclass(frozen=True)
class _PromptBudgetInputs:
    messages: list[Any]
    message_count: int
    policy_path: str
    stage: str
    require_backend_tokenizer: bool
    prompt_metadata: dict[str, Any]
    counter: Any
    known_async_counter: bool


async def maybe_record_prompt_budget(
    *,
    destination: TurnArtifactDestination,
    prompt_hash: str,
    messages: list[dict[str, str]],
    context: dict[str, Any],
    model_client: Any,
) -> dict[str, Any] | None:
    prompt_budget_enabled = bool(context.get("prompt_budget_enabled", context.get("protocol_governed_enabled", False)))
    if not prompt_budget_enabled:
        return None

    captured_prompt_hash = str(prompt_hash or "")
    captured = _capture_prompt_budget_inputs(messages=messages, context=context, model_client=model_client)
    prompt_budget_result = await _evaluate_prompt_budget(captured)
    prompt_structure = build_prompt_structure_payload(
        context={"prompt_metadata": captured.prompt_metadata},
        prompt_hash=captured_prompt_hash,
        message_count=captured.message_count,
        budget_result=prompt_budget_result,
    )
    usage_json = json.dumps(prompt_budget_result, indent=2, ensure_ascii=False)
    structure_json = json.dumps(prompt_structure, indent=2, ensure_ascii=False)
    await run_owned_thread(
        lambda: write_prompt_budget_artifacts(
            destination=destination,
            prompt_budget_usage_json=usage_json,
            prompt_structure_json=structure_json,
            prompt_structure=dict(prompt_structure),
        ),
        label="prompt-budget-artifact-batch",
    )
    return prompt_budget_result


async def evaluate_prompt_budget(
    *,
    messages: list[dict[str, str]],
    context: dict[str, Any],
    model_client: Any,
) -> dict[str, Any]:
    captured = _capture_prompt_budget_inputs(messages=messages, context=context, model_client=model_client)
    return await _evaluate_prompt_budget(captured)


def _capture_prompt_budget_inputs(
    *, messages: list[dict[str, str]], context: dict[str, Any], model_client: Any,
) -> _PromptBudgetInputs:
    captured_messages = [dict(row) if isinstance(row, dict) else row for row in messages]
    policy_path = str(
        context.get("prompt_budget_policy_path") or str(contract_assets.DEFAULT_PROMPT_BUDGET_PATH)
    ).strip()
    prompt_metadata = context.get("prompt_metadata")
    prompt_metadata = dict(prompt_metadata) if isinstance(prompt_metadata, dict) else {}
    counter = resolve_token_counter(model_client)
    return _PromptBudgetInputs(
        messages=captured_messages,
        message_count=len(captured_messages),
        policy_path=str(capture_file_roots([Path(policy_path)])[0]),
        stage=resolve_prompt_stage(context),
        require_backend_tokenizer=bool(context.get("prompt_budget_require_backend_tokenizer", False)),
        prompt_metadata=prompt_metadata,
        counter=counter,
        known_async_counter=is_known_async_counter(counter),
    )


async def _evaluate_prompt_budget(captured: _PromptBudgetInputs) -> dict[str, Any]:
    policy = await run_owned_thread(
        lambda: load_prompt_budget_policy(captured.policy_path),
        label="prompt-budget-policy-load",
    )
    stage_limits = dict(policy["stages"][captured.stage])

    protocol_messages, tool_schema_messages, task_messages = _partition_prompt_messages(captured.messages)
    token_stats = await count_prompt_token_buckets(
        counter=captured.counter,
        known_async_counter=captured.known_async_counter,
        messages=captured.messages,
        protocol_messages=protocol_messages,
        tool_schema_messages=tool_schema_messages,
        task_messages=task_messages,
        require_backend_tokenizer=captured.require_backend_tokenizer,
    )
    if token_stats.get("error"):
        return {
            "ok": False,
            "error": token_stats["error"],
            "stage": captured.stage,
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
                    f"{captured.stage}:{key}:{usage[key]}>{stage_limits[key]}",
                ),
                "stage": captured.stage,
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
        "stage": captured.stage,
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
    messages: list[Any],
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
