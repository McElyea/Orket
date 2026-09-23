from __future__ import annotations

from typing import Any

from .turn_artifact_destination import TurnArtifactDestination
from .turn_memory_trace_artifacts import (
    MemoryTraceInputs,
    append_memory_event,
    publish_memory_trace,
    render_memory_trace_publication,
)


async def emit_turn_memory_traces(
    *, destination: TurnArtifactDestination, memory_inputs: MemoryTraceInputs,
    memory_events: list[dict[str, Any]] | None, context: dict[str, Any], current_turn: Any,
    failure_reason: str = "", failure_type: str = "",
) -> None:
    publication = render_memory_trace_publication(
        destination=destination, inputs=memory_inputs, event_sink=memory_events, turn=current_turn,
        guardrails_triggered=context.get("guardrails_triggered"),
        retrieval_events=context.get("memory_retrieval_trace_events"),
        failure_reason=failure_reason, failure_type=failure_type,
    )
    await publish_memory_trace(destination=destination, publication=publication)


async def emit_turn_failure_traces(
    *, destination: TurnArtifactDestination, memory_inputs: MemoryTraceInputs,
    memory_events: list[dict[str, Any]] | None, context: dict[str, Any], current_turn: Any,
    error: str, failure_type: str,
) -> None:
    append_memory_event(memory_events, role_name=destination.role_name, interceptor="on_turn_failure",
                        decision_type=str(failure_type).strip() or "turn_failed")
    await emit_turn_memory_traces(
        destination=destination, memory_inputs=memory_inputs, memory_events=memory_events,
        context=context, current_turn=current_turn,
        failure_reason=str(error or "").strip() or "turn_failed",
        failure_type=str(failure_type or "").strip() or "turn_failed",
    )
