from __future__ import annotations

from functools import partial
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.logging import log_event

from .turn_artifact_destination import TurnArtifactDestination
from .turn_response_capture import CapturedTurnResponse


async def write_response_artifacts(
    *, destination: TurnArtifactDestination, response: CapturedTurnResponse,
) -> None:
    await run_owned_thread(
        partial(destination.writer.write_turn_artifact, destination=destination,
                filename="model_response.txt", content=response.text_artifact_content),
        label="turn-response-text",
    )
    await run_owned_thread(
        partial(destination.writer.write_turn_artifact, destination=destination,
                filename="model_response_raw.json", content=response.raw_artifact_content),
        label="turn-response-raw",
    )


def log_turn_start(
    *,
    destination: TurnArtifactDestination,
    context: dict[str, Any],
    turn_trace_id: str,
    prompt_hash: str,
    messages: list[dict[str, str]],
    prompt_budget_result: Any,
) -> None:
    log_event(
        "turn_start",
        {
            "issue_id": destination.issue_id,
            "role": destination.role_name,
            "session_id": destination.session_id,
            "turn_index": destination.turn_index,
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
            "odr_termination_reason": context.get("odr_termination_reason"),
            "odr_final_auditor_verdict": context.get("odr_final_auditor_verdict"),
            "odr_artifact_path": context.get("odr_artifact_path"),
            "prompt_budget_stage": (prompt_budget_result or {}).get("stage"),
            "prompt_budget_tokenizer_id": (prompt_budget_result or {}).get("tokenizer_id"),
        },
        destination.workspace,
    )


__all__ = [
    "log_turn_start",
    "write_response_artifacts",
]
