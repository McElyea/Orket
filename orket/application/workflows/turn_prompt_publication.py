"""Capture initial prompt artifacts and admit their writes in order."""
from __future__ import annotations

import json
from functools import partial
from typing import TYPE_CHECKING, Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.logging import log_event

from .prompt_budget_guard import maybe_record_prompt_budget
from .turn_artifact_destination import TurnArtifactDestination
from .turn_contract_input_capture import capture_mapping
from .turn_executor_model_artifacts import log_turn_start

if TYPE_CHECKING:
    from .turn_executor import TurnResult
    from .turn_executor_model_flow import FailedResultFactory, FailureEmitter


async def prepare_prompt_and_write_artifacts(
    *, destination: TurnArtifactDestination,
    model_client: Any, context: dict[str, Any], messages: list[dict[str, str]],
    turn_trace_id: str,
    emit_failure: FailureEmitter, turn_result_failed: FailedResultFactory,
) -> tuple[list[dict[str, str]], str, TurnResult | None]:
    captured = capture_mapping({"messages": messages, "layers": context.get("prompt_layers", {})})
    messages = captured["messages"]
    prompt_hash = destination.writer.message_hash(messages)
    budget = await maybe_record_prompt_budget(
        destination=destination, prompt_hash=prompt_hash, messages=messages,
        context=context, model_client=model_client,
    )
    if isinstance(budget, dict) and not bool(budget.get("ok", False)):
        error = str(budget.get("error") or "E_PROMPT_BUDGET_EXCEEDED")
        log_event("turn_failed", {
            "issue_id": destination.issue_id, "role": destination.role_name,
            "session_id": destination.session_id, "turn_index": destination.turn_index,
            "turn_trace_id": turn_trace_id, "type": "prompt_budget_exceeded",
            "error": error, "prompt_budget_usage": budget,
        }, destination.workspace)
        await emit_failure(error, "prompt_budget_exceeded", None)
        return messages, "", turn_result_failed(error, False)
    log_turn_start(
        destination=destination, context=context,
        turn_trace_id=turn_trace_id, prompt_hash=prompt_hash, messages=messages,
        prompt_budget_result=budget,
    )
    messages_content = json.dumps(messages, indent=2, ensure_ascii=False)
    layers_content = json.dumps(captured["layers"], indent=2, ensure_ascii=False, default=str)
    await run_owned_thread(partial(destination.writer.write_turn_artifact,
        destination=destination, filename="messages.json", content=messages_content), label="turn-messages")
    await run_owned_thread(partial(destination.writer.write_turn_artifact,
        destination=destination, filename="prompt_layers.json", content=layers_content), label="turn-prompt-layers")
    return messages, prompt_hash, None
