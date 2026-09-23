"""Captured memory-trace inputs, event accumulation, rendering and publication."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import partial
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.core.domain.execution import ExecutionTurn

from .turn_artifact_destination import TurnArtifactDestination
from .turn_contract_input_capture import capture_mapping


@dataclass(frozen=True, slots=True)
class MemoryTraceInputs:
    enabled: bool
    normalization_version: str
    tool_profile_version: str
    event_normalization_version: str
    event_tool_profile_version: str
    workflow_id: str
    memory_snapshot_id: str
    visibility_mode: str
    model_config_id: str
    policy_set_id: str
    output_type: str


@dataclass(frozen=True, slots=True)
class MemoryTracePublication:
    memory_trace: str
    retrieval_trace: str


def _normalized(value: Any, default: str) -> str:
    return str(value or default).strip() or default


def capture_memory_trace_inputs(context: dict[str, Any]) -> MemoryTraceInputs:
    """Capture only scalar configuration consumed by one turn's memory trace."""
    enabled = bool(context.get("memory_trace_enabled", False))
    if not enabled:
        enabled = str(context.get("visibility_mode", "")).strip() != ""
    if not enabled:
        return MemoryTraceInputs(
            enabled=False,
            normalization_version="json-v1",
            tool_profile_version="unknown-v1",
            event_normalization_version="json-v1",
            event_tool_profile_version="unknown-v1",
            workflow_id="turn_executor",
            memory_snapshot_id="unknown",
            visibility_mode="off",
            model_config_id="unknown",
            policy_set_id="unknown",
            output_type="",
        )
    normalization = context.get("normalization_version") or "json-v1"
    profile = context.get("tool_profile_version") or "unknown-v1"
    model = context.get("model_config_id") or context.get("selected_model") or "unknown"
    return MemoryTraceInputs(
        enabled=True,
        normalization_version=_normalized(normalization, "json-v1"),
        tool_profile_version=_normalized(profile, "unknown-v1"),
        event_normalization_version=str(normalization),
        event_tool_profile_version=str(profile),
        workflow_id=_normalized(context.get("workflow_id"), "turn_executor"),
        memory_snapshot_id=_normalized(context.get("memory_snapshot_id"), "unknown"),
        visibility_mode=_normalized(context.get("visibility_mode"), "off"),
        model_config_id=_normalized(model, "unknown"),
        policy_set_id=_normalized(context.get("policy_set_id"), "unknown"),
        output_type=str(context.get("output_type") or "").strip(),
    )


def admit_memory_trace_event_sink(
    *, context: dict[str, Any], inputs: MemoryTraceInputs,
) -> list[dict[str, Any]] | None:
    """Publish the invocation's original event list after execution-owner admission."""
    if not inputs.enabled:
        return None
    event_sink: list[dict[str, Any]] = []
    context["_memory_trace_events"] = event_sink
    return event_sink


def append_memory_event(
    event_sink: list[dict[str, Any]] | None,
    *,
    role_name: str,
    interceptor: str,
    decision_type: str,
    tool_calls: list[dict[str, Any]] | None = None,
    guardrails_triggered: list[str] | None = None,
    retrieval_event_ids: list[str] | None = None,
) -> None:
    if event_sink is None:
        return
    row = {
        "role": role_name,
        "interceptor": str(interceptor).strip(),
        "decision_type": str(decision_type).strip(),
        "tool_calls": list(tool_calls or []),
        "guardrails_triggered": list(guardrails_triggered or []),
        "retrieval_event_ids": list(retrieval_event_ids or []),
    }
    event_sink.append(capture_mapping(row))


def _trace_tool_calls(
    destination: TurnArtifactDestination,
    inputs: MemoryTraceInputs,
    turn: ExecutionTurn | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for call in (turn.tool_calls if turn is not None else []) or []:
        result = capture_mapping(call.result) if isinstance(call.result, dict) else {}
        rows.append({
            "tool_name": str(call.tool or "").strip(),
            "tool_profile_version": inputs.tool_profile_version,
            "normalized_args": capture_mapping(dict(call.args or {})),
            "normalization_version": inputs.normalization_version,
            "tool_result_fingerprint": destination.writer.hash_payload(result),
            "side_effect_fingerprint": None,
        })
    return rows


def _trace_events(
    destination: TurnArtifactDestination,
    event_sink: list[dict[str, Any]] | None,
    fallback_tool_calls: list[dict[str, Any]],
    guardrails_triggered: list[str],
    retrieval_events: list[dict[str, Any]],
    failure_reason: str,
    failure_type: str,
) -> list[dict[str, Any]]:
    captured = [capture_mapping(event) for event in (event_sink or [])]
    if captured:
        return [{
            "event_id": (
                f"{destination.session_id}:{destination.issue_id}:"
                f"{destination.role_name}:{destination.turn_index}:{index}"
            ),
            "index": index,
            "role": str(event.get("role", destination.role_name)),
            "interceptor": str(event.get("interceptor", "turn")),
            "decision_type": str(event.get("decision_type", "execute_turn")),
            "tool_calls": list(event.get("tool_calls") or []),
            "guardrails_triggered": list(event.get("guardrails_triggered") or []),
            "retrieval_event_ids": list(event.get("retrieval_event_ids") or []),
        } for index, event in enumerate(captured)]
    retrieval_ids = [
        str((row or {}).get("retrieval_event_id", "")).strip()
        for row in retrieval_events
        if str((row or {}).get("retrieval_event_id", "")).strip()
    ]
    decision_type = str(failure_type).strip() if failure_reason else "execute_turn"
    return [{
        "event_id": (
            f"{destination.session_id}:{destination.issue_id}:"
            f"{destination.role_name}:{destination.turn_index}:0"
        ),
        "index": 0,
        "role": destination.role_name,
        "interceptor": "on_turn_failure" if failure_reason else "turn",
        "decision_type": decision_type or "execute_turn",
        "tool_calls": fallback_tool_calls,
        "guardrails_triggered": guardrails_triggered,
        "retrieval_event_ids": retrieval_ids,
    }]


def _output_payload(
    destination: TurnArtifactDestination,
    inputs: MemoryTraceInputs,
    failure_reason: str,
    failure_type: str,
) -> dict[str, Any]:
    output_type = inputs.output_type or ("error" if failure_reason else "text")
    shape: dict[str, Any] = {"type": output_type}
    if failure_reason:
        shape.update(status="failed", failure_type=str(failure_type).strip() or "turn_failed")
    elif output_type == "text":
        shape["sections"] = ["body"]
    return {
        "output_type": output_type,
        "output_shape_hash": destination.writer.hash_payload(shape),
        "normalization_version": inputs.normalization_version,
    }


def render_memory_trace_publication(
    *,
    destination: TurnArtifactDestination,
    inputs: MemoryTraceInputs,
    event_sink: list[dict[str, Any]] | None,
    turn: ExecutionTurn | None,
    guardrails_triggered: list[str] | None,
    retrieval_events: list[dict[str, Any]] | None,
    failure_reason: str = "",
    failure_type: str = "",
) -> MemoryTracePublication | None:
    if not inputs.enabled:
        return None
    if destination.role_id is None:
        raise ValueError("E_TURN_MEMORY_ROLE_ID_REQUIRED")
    retrieval = capture_mapping({"events": list(retrieval_events or [])})["events"]
    guardrails = list(guardrails_triggered or [])
    fallback_calls = _trace_tool_calls(destination, inputs, turn)
    events = _trace_events(
        destination, event_sink, fallback_calls, guardrails,
        retrieval, failure_reason, failure_type,
    )
    memory_trace = {
        "run_id": destination.session_id,
        "workflow_id": inputs.workflow_id,
        "memory_snapshot_id": inputs.memory_snapshot_id,
        "visibility_mode": inputs.visibility_mode,
        "model_config_id": inputs.model_config_id,
        "policy_set_id": inputs.policy_set_id,
        "determinism_trace_schema_version": "memory.determinism_trace.v1",
        "events": events,
        "output": _output_payload(destination, inputs, failure_reason, failure_type),
        "issue_id": destination.issue_id,
        "role_id": destination.role_id,
        "metadata": {"truncated": False},
    }
    retrieval_trace = {
        "events": retrieval,
        "retrieval_trace_schema_version": "memory.retrieval_trace.v1",
        "metadata": {"truncated": False},
    }
    return MemoryTracePublication(
        memory_trace=json.dumps(memory_trace, indent=2, ensure_ascii=False, default=str),
        retrieval_trace=json.dumps(retrieval_trace, indent=2, ensure_ascii=False, default=str),
    )


async def publish_memory_trace(
    *, destination: TurnArtifactDestination, publication: MemoryTracePublication | None,
) -> None:
    if publication is None:
        return
    await run_owned_thread(
        partial(
            destination.writer.write_memory_trace_publication,
            destination=destination,
            publication=publication,
        ),
        label="turn-memory-trace-publication",
    )
