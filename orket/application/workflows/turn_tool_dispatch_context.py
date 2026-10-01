"""Per-invocation dispatch values and progress; effects remain on the selected dispatcher."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneService
from orket.core.contracts.card_completion_commit import is_card_completion_call
from orket.core.contracts.protocol_hashing import (
    VALIDATOR_VERSION,
    build_step_id,
    default_protocol_hash,
    default_tool_schema_hash,
    derive_operation_id,
    derive_step_seed,
    hash_canonical_json,
)
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.schema import IssueConfig

from .turn_artifact_destination import TurnArtifactDestination
from .turn_control_plane_binding import TurnControlPlaneBinding
from .turn_memory_trace_artifacts import MemoryTraceInputs
from .turn_tool_dispatcher_support import build_execution_capsule, resolve_skill_tool_binding

if TYPE_CHECKING:
    from .turn_tool_dispatcher import ToolDispatcher


@dataclass
class DispatchRun:
    owner: ToolDispatcher
    turn: ExecutionTurn
    toolbox: Any
    context: dict[str, Any]
    workspace: Path
    destination: TurnArtifactDestination
    memory_inputs: MemoryTraceInputs
    memory_events: list[dict[str, Any]] | None
    control_plane: TurnControlPlaneBinding
    issue: IssueConfig | None
    control_plane_service: TurnToolControlPlaneService | None
    violations: list[str]
    roles: list[str]
    session_id: str
    turn_index: int
    step_id: str
    step_seed: str
    proposal_hash: str
    validator_version: str
    protocol_hash: str
    tool_schema_hash: str
    protocol_enabled: bool
    protocol_replay_mode: bool
    control_plane_enabled: bool
    execution_capsule: dict[str, Any]
    approval_required_tools: set[str]
    request_writer: object
    approval_resolver: object
    control_plane_run_id: str | None = None
    control_plane_attempt_id: str | None = None
    executed_step_count: int = 0
    last_result_ref: str | None = None


@dataclass(frozen=True)
class DispatchStep:
    index: int
    tool_call: ToolCall
    operation_id: str
    receipt_seq: int
    tool_name: str
    binding: dict[str, Any] | None


def capture_dispatch_run(
    self: ToolDispatcher,
    *,
    turn: ExecutionTurn,
    toolbox: Any,
    context: dict[str, Any],
    workspace: Path,
    destination: TurnArtifactDestination,
    memory_inputs: MemoryTraceInputs,
    control_plane: TurnControlPlaneBinding,
    memory_events: list[dict[str, Any]] | None,
    issue: IssueConfig | None = None,
) -> DispatchRun:
    control_plane_service = control_plane.service
    violations: list[str] = []
    roles = context.get("roles", [turn.role])
    session_id = str(context.get("session_id", "unknown-session"))
    turn_index = int(context.get("turn_index", 0))
    step_id = build_step_id(issue_id=turn.issue_id, turn_index=turn_index)
    run_seed = str(context.get("run_seed") or session_id)
    step_seed = derive_step_seed(run_seed=run_seed, run_id=session_id, step_id=step_id)
    raw_payload = turn.raw if isinstance(turn.raw, dict) else {}
    proposal_hash = _capture_proposal_hash(turn, raw_payload)
    validator_version = str(
        raw_payload.get("validator_version") or context.get("validator_version") or VALIDATOR_VERSION
    )
    protocol_hash = str(raw_payload.get("protocol_hash") or context.get("protocol_hash") or default_protocol_hash())
    tool_schema_hash = str(
        raw_payload.get("tool_schema_hash") or context.get("tool_schema_hash") or default_tool_schema_hash()
    )
    protocol_enabled = bool(context.get("protocol_governed_enabled", False))
    protocol_replay_mode = bool(context.get("protocol_replay_mode"))
    control_plane_enabled = _use_control_plane(turn, protocol_replay_mode, control_plane_service)
    execution_capsule = build_execution_capsule(context)
    approval_required_tools = {
        str(tool).strip() for tool in context.get("approval_required_tools") or [] if str(tool).strip()
    }
    request_writer = context.get("create_pending_gate_request")
    approval_resolver = context.get("resolve_granted_tool_approval")
    return DispatchRun(
        owner=self,
        turn=turn,
        toolbox=toolbox,
        context=context,
        workspace=workspace,
        destination=destination,
        memory_inputs=memory_inputs,
        memory_events=memory_events,
        control_plane=control_plane,
        issue=issue,
        control_plane_service=control_plane_service,
        violations=violations,
        roles=roles,
        session_id=session_id,
        turn_index=turn_index,
        step_id=step_id,
        step_seed=step_seed,
        proposal_hash=proposal_hash,
        validator_version=validator_version,
        protocol_hash=protocol_hash,
        tool_schema_hash=tool_schema_hash,
        protocol_enabled=protocol_enabled,
        protocol_replay_mode=protocol_replay_mode,
        control_plane_enabled=control_plane_enabled,
        execution_capsule=execution_capsule,
        approval_required_tools=approval_required_tools,
        request_writer=request_writer,
        approval_resolver=approval_resolver,
    )


def capture_dispatch_step(run: DispatchRun, index: int, tool_call: ToolCall) -> DispatchStep:
    operation_id = derive_operation_id(run_id=run.session_id, step_id=run.step_id, tool_index=index)
    receipt_seq = index + 1
    tool_name = str(tool_call.tool or "")
    binding = resolve_skill_tool_binding(run.context, tool_name)
    return DispatchStep(index, tool_call, operation_id, receipt_seq, tool_name, binding)


def _capture_proposal_hash(turn: ExecutionTurn, raw_payload: dict[str, Any]) -> str:
    proposal_hash = str(raw_payload.get("proposal_hash") or "")
    if not proposal_hash:
        proposal_hash = hash_canonical_json(
            {
                "content": str(turn.content or ""),
                "tool_calls": [
                    {"tool": str(call.tool or ""), "args": dict(call.args or {})}
                    for call in list(turn.tool_calls or [])
                ],
            }
        )
    return proposal_hash


def _use_control_plane(
    turn: ExecutionTurn, protocol_replay_mode: bool, control_plane_service: TurnToolControlPlaneService | None
) -> bool:
    control_plane_enabled = not protocol_replay_mode and control_plane_service is not None
    if control_plane_enabled and turn.tool_calls:
        tool_names = [str(call.tool or "").strip() for call in turn.tool_calls if str(call.tool or "").strip()]
        if (
            tool_names
            and all(name == "update_issue_status" for name in tool_names)
            and (not any(is_card_completion_call(call.tool, call.args) for call in turn.tool_calls))
        ):
            control_plane_enabled = False
    return control_plane_enabled
