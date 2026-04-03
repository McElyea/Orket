from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from orket.logging import log_event
from orket.schema import IssueConfig, RoleConfig

if TYPE_CHECKING:
    from .turn_executor import TurnExecutor


def response_artifact_payload(response: Any) -> tuple[str, Any]:
    response_content = (
        getattr(response, "content", "") if not isinstance(response, dict) else response.get("content", "")
    )
    response_raw = getattr(response, "raw", {}) if not isinstance(response, dict) else response
    return response_content or "", response_raw


async def write_response_artifacts(
    executor: TurnExecutor,
    *,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
    response: Any,
) -> None:
    response_content, response_raw = response_artifact_payload(response)
    await asyncio.to_thread(
        executor.artifact_writer.write_turn_artifact,
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index,
        filename="model_response.txt",
        content=response_content,
    )
    await asyncio.to_thread(
        executor.artifact_writer.write_turn_artifact,
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index,
        filename="model_response_raw.json",
        content=json.dumps(response_raw, indent=2, ensure_ascii=False, default=str),
    )


def log_turn_start(
    *,
    executor: TurnExecutor,
    issue: IssueConfig,
    role: RoleConfig,
    context: dict[str, Any],
    session_id: str,
    turn_index: int,
    turn_trace_id: str,
    prompt_hash: str,
    messages: list[dict[str, str]],
    prompt_budget_result: Any,
) -> None:
    log_event(
        "turn_start",
        {
            "issue_id": issue.id,
            "role": role.name,
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
            "profile_traits": context.get("profile_traits"),
            "seat_coercion": context.get("seat_coercion"),
            "artifact_contract": context.get("artifact_contract"),
            "scenario_truth": context.get("scenario_truth"),
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


__all__ = [
    "log_turn_start",
    "response_artifact_payload",
    "write_response_artifacts",
]
