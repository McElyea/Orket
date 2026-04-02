from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.application.services.turn_tool_control_plane_service import (
    TurnToolControlPlaneError,
    TurnToolControlPlaneService,
)
from orket.application.services.turn_tool_control_plane_support import (
    effect_id_for,
    run_namespace_scope,
    tool_authorization_ref,
    tool_operation_ref,
    tool_result_ref,
)
from orket.application.workflows.protocol_hashing import build_step_id, derive_operation_id
from orket.core.domain.control_plane_effect_journal import validate_effect_journal_chain
from orket.domain.execution import ToolCall

if TYPE_CHECKING:
    from .turn_executor import TurnExecutor


async def load_checkpoint_snapshot_payload(
    *,
    executor: TurnExecutor,
    issue_id: str,
    role_name: str,
    context: dict[str, Any],
    state_snapshot_ref: str,
) -> dict[str, Any]:
    snapshot_token = str(state_snapshot_ref or "").strip().split(":")[-1]
    if not snapshot_token:
        raise TurnToolControlPlaneError("governed turn checkpoint replay is missing snapshot identity")
    snapshot_path = turn_output_dir(
        executor=executor,
        issue_id=issue_id,
        role_name=role_name,
        context=context,
    ) / f"control_plane_checkpoint_snapshot_{snapshot_token}.json"
    payload = await asyncio.to_thread(_read_json_file, snapshot_path)
    if not isinstance(payload, dict):
        raise TurnToolControlPlaneError(
            f"governed turn checkpoint replay is missing immutable checkpoint snapshot artifact: {snapshot_path.name}"
        )
    if not isinstance(payload.get("tool_calls"), list):
        raise TurnToolControlPlaneError(
            f"governed turn checkpoint snapshot is malformed for replay: {snapshot_path.name}"
        )
    return payload


def validate_snapshot_identity(
    *,
    snapshot_payload: dict[str, Any],
    issue_id: str,
    role_name: str,
    context: dict[str, Any],
    error_prefix: str,
) -> str:
    expected_session_id = str(context.get("session_id", "unknown-session"))
    expected_turn_index = int(context.get("turn_index", 0))
    expected_namespace_scope = run_namespace_scope(issue_id=issue_id, context=context)
    observed_role = str(snapshot_payload.get("role") or "").strip()
    observed_issue = str(snapshot_payload.get("issue_id") or "").strip()
    observed_run = str(snapshot_payload.get("run_id") or "").strip()
    observed_turn_index = snapshot_payload.get("turn_index")
    observed_namespace_scope = str(snapshot_payload.get("namespace_scope") or "").strip()

    if observed_run != expected_session_id:
        raise TurnToolControlPlaneError(f"{error_prefix} snapshot run identity does not match current request")
    if observed_issue != issue_id:
        raise TurnToolControlPlaneError(f"{error_prefix} snapshot issue identity does not match current request")
    if observed_role != role_name:
        raise TurnToolControlPlaneError(f"{error_prefix} snapshot role identity does not match current request")
    if observed_turn_index != expected_turn_index:
        raise TurnToolControlPlaneError(f"{error_prefix} snapshot turn index does not match current request")
    if observed_namespace_scope != expected_namespace_scope:
        raise TurnToolControlPlaneError(f"{error_prefix} snapshot namespace scope does not match current request")
    return expected_namespace_scope


def planned_tool_calls_from_snapshot(
    snapshot_payload: dict[str, Any],
    *,
    error_prefix: str,
) -> list[dict[str, Any]]:
    tool_calls = snapshot_payload.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        raise TurnToolControlPlaneError(f"{error_prefix} snapshot is missing a replayable tool plan")
    normalized_calls: list[dict[str, Any]] = []
    for raw_tool_call in tool_calls:
        if not isinstance(raw_tool_call, dict):
            raise TurnToolControlPlaneError(f"{error_prefix} snapshot tool plan is malformed for replay")
        tool_name = str(raw_tool_call.get("tool") or "").strip()
        tool_args = raw_tool_call.get("args")
        if not tool_name or not isinstance(tool_args, dict):
            raise TurnToolControlPlaneError(f"{error_prefix} snapshot tool plan is malformed for replay")
        normalized_calls.append({"tool": tool_name, "args": tool_args})
    return normalized_calls


def planned_tool_call_objects(
    snapshot_payload: dict[str, Any],
    *,
    error_prefix: str,
) -> list[ToolCall]:
    return [
        ToolCall(tool=tool_call["tool"], args=tool_call["args"], result=None, error=None)
        for tool_call in planned_tool_calls_from_snapshot(snapshot_payload, error_prefix=error_prefix)
    ]


def expected_operation_ids(
    *,
    issue_id: str,
    context: dict[str, Any],
    tool_call_count: int,
) -> list[str]:
    step_id = build_step_id(issue_id=issue_id, turn_index=int(context.get("turn_index", 0)))
    session_id = str(context.get("session_id", "unknown-session"))
    return [
        derive_operation_id(run_id=session_id, step_id=step_id, tool_index=index)
        for index in range(tool_call_count)
    ]


async def list_operation_artifact_ids(
    *,
    executor: TurnExecutor,
    issue_id: str,
    role_name: str,
    context: dict[str, Any],
) -> list[str]:
    operations_dir = (
        turn_output_dir(
            executor=executor,
            issue_id=issue_id,
            role_name=role_name,
            context=context,
        )
        / "operations"
    )
    return await asyncio.to_thread(_list_operation_artifact_ids, operations_dir)


async def list_operation_artifact_refs(
    *,
    executor: TurnExecutor,
    issue_id: str,
    role_name: str,
    context: dict[str, Any],
) -> list[str]:
    return [tool_operation_ref(operation_id=operation_id) for operation_id in await list_operation_artifact_ids(
        executor=executor,
        issue_id=issue_id,
        role_name=role_name,
        context=context,
    )]


async def load_completed_replay_tool_calls(
    *,
    executor: TurnExecutor,
    control_plane_service: TurnToolControlPlaneService,
    run_id: str,
    attempt_id: str,
    issue_id: str,
    role_name: str,
    context: dict[str, Any],
    snapshot_payload: dict[str, Any],
) -> list[ToolCall]:
    namespace_scope = validate_snapshot_identity(
        snapshot_payload=snapshot_payload,
        issue_id=issue_id,
        role_name=role_name,
        context=context,
        error_prefix="completed governed turn checkpoint",
    )
    planned_tool_calls = planned_tool_calls_from_snapshot(
        snapshot_payload,
        error_prefix="completed governed turn checkpoint",
    )
    expected_ids = expected_operation_ids(
        issue_id=issue_id,
        context=context,
        tool_call_count=len(planned_tool_calls),
    )
    artifact_ids = await list_operation_artifact_ids(
        executor=executor,
        issue_id=issue_id,
        role_name=role_name,
        context=context,
    )
    if set(artifact_ids) != set(expected_ids):
        raise TurnToolControlPlaneError(
            "completed governed turn durable operation artifacts do not match checkpoint tool plan for replay"
        )

    steps = await control_plane_service.execution_repository.list_step_records(attempt_id=attempt_id)
    steps_by_id = {step.step_id: step for step in steps}
    if set(steps_by_id) != set(expected_ids):
        raise TurnToolControlPlaneError(
            "completed governed turn durable step truth does not match checkpoint tool plan for replay"
        )

    effect_entries = await control_plane_service.publication.repository.list_effect_journal_entries(run_id=run_id)
    if effect_entries:
        validate_effect_journal_chain(effect_entries)
    attempt_effects = [entry for entry in effect_entries if entry.attempt_id == attempt_id]
    effects_by_id = {entry.effect_id: entry for entry in attempt_effects}
    expected_effect_ids = {effect_id_for(operation_id=operation_id) for operation_id in expected_ids}
    if set(effects_by_id) != expected_effect_ids:
        raise TurnToolControlPlaneError(
            "completed governed turn durable effect truth does not match checkpoint tool plan for replay"
        )

    session_id = str(context.get("session_id", "unknown-session"))
    turn_index = int(context.get("turn_index", 0))
    tool_calls: list[ToolCall] = []
    for planned_tool_call, operation_id in zip(planned_tool_calls, expected_ids, strict=True):
        step = steps_by_id[operation_id]
        effect = effects_by_id[effect_id_for(operation_id=operation_id)]
        operation_record = await asyncio.to_thread(
            executor.artifact_writer.load_operation_result,
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            operation_id=operation_id,
        )
        if not isinstance(operation_record, dict):
            raise TurnToolControlPlaneError(
                f"completed governed turn step {operation_id} is missing durable operation truth for artifact replay"
            )
        result = operation_record.get("result")
        if not isinstance(result, dict):
            raise TurnToolControlPlaneError(
                f"completed governed turn step {operation_id} has malformed operation truth for artifact replay"
            )
        if str(operation_record.get("tool") or "").strip() != planned_tool_call["tool"]:
            raise TurnToolControlPlaneError(
                f"completed governed turn step {operation_id} does not match checkpoint tool plan for replay"
            )
        if operation_record.get("args") != planned_tool_call["args"]:
            raise TurnToolControlPlaneError(
                f"completed governed turn step {operation_id} arguments do not match checkpoint tool plan for replay"
            )
        _validate_step_effect_alignment(
            step=step,
            effect=effect,
            operation_id=operation_id,
            attempt_id=attempt_id,
            namespace_scope=namespace_scope,
            fallback_tool_name=planned_tool_call["tool"],
        )
        tool_calls.append(
            ToolCall(
                tool=planned_tool_call["tool"],
                args=planned_tool_call["args"],
                result=result,
                error=str(result.get("error") or "").strip() or None,
            )
        )
    return tool_calls


def turn_output_dir(
    *,
    executor: TurnExecutor,
    issue_id: str,
    role_name: str,
    context: dict[str, Any],
) -> Path:
    resolver = getattr(executor.artifact_writer, "_turn_output_dir", None)
    if not callable(resolver):
        raise TurnToolControlPlaneError("turn artifact writer does not expose turn output resolution")
    return resolver(
        session_id=str(context.get("session_id", "unknown-session")),
        issue_id=issue_id,
        role_name=role_name,
        turn_index=int(context.get("turn_index", 0)),
    )


def _validate_step_effect_alignment(
    *,
    step: Any,
    effect: Any,
    operation_id: str,
    attempt_id: str,
    namespace_scope: str,
    fallback_tool_name: str,
) -> None:
    expected_output_ref = tool_result_ref(operation_id=operation_id)
    expected_operation_ref = tool_operation_ref(operation_id=operation_id)
    expected_effect_id = effect_id_for(operation_id=operation_id)
    if str(step.output_ref or "") != expected_output_ref:
        raise TurnToolControlPlaneError(
            f"completed governed turn step {operation_id} output ref does not align with durable operation truth"
        )
    if str(step.namespace_scope or "") != namespace_scope:
        raise TurnToolControlPlaneError(
            f"completed governed turn step {operation_id} namespace scope does not align with checkpoint truth"
        )
    if expected_operation_ref not in list(getattr(step, "receipt_refs", []) or []):
        raise TurnToolControlPlaneError(
            f"completed governed turn step {operation_id} is missing durable receipt truth for artifact replay"
        )
    tool_call_prefix = "turn-tool-call:"
    step_input_ref = str(step.input_ref or "").strip()
    if not step_input_ref.startswith(tool_call_prefix):
        raise TurnToolControlPlaneError(
            f"completed governed turn step {operation_id} input ref is malformed for artifact replay"
        )
    if step_input_ref not in list(getattr(step, "receipt_refs", []) or []):
        raise TurnToolControlPlaneError(
            f"completed governed turn step {operation_id} is missing durable tool-call receipt truth for artifact replay"
        )
    expected_authorization_ref = tool_authorization_ref(
        tool_call_digest=step_input_ref[len(tool_call_prefix) :],
    )
    expected_target_ref = list(getattr(step, "resources_touched", []) or [])
    expected_target = expected_target_ref[0] if expected_target_ref else f"tool:{fallback_tool_name}"
    if effect.effect_id != expected_effect_id:
        raise TurnToolControlPlaneError(
            f"completed governed turn effect truth for {operation_id} does not align with durable step truth"
        )
    if effect.step_id != step.step_id or effect.attempt_id != attempt_id:
        raise TurnToolControlPlaneError(
            f"completed governed turn effect truth for {operation_id} does not align with attempt lineage"
        )
    if effect.authorization_basis_ref != expected_authorization_ref:
        raise TurnToolControlPlaneError(
            f"completed governed turn effect truth for {operation_id} does not align with durable authorization truth"
        )
    if effect.integrity_verification_ref != expected_operation_ref:
        raise TurnToolControlPlaneError(
            f"completed governed turn effect truth for {operation_id} does not align with durable receipt truth"
        )
    if effect.observed_result_ref != expected_output_ref:
        raise TurnToolControlPlaneError(
            f"completed governed turn effect truth for {operation_id} does not align with durable output truth"
        )
    if effect.intended_target_ref != expected_target:
        raise TurnToolControlPlaneError(
            f"completed governed turn effect truth for {operation_id} does not align with durable target truth"
        )


def _list_operation_artifact_ids(operations_dir: Path) -> list[str]:
    if not operations_dir.exists():
        return []
    return sorted(path.stem for path in operations_dir.glob("*.json") if path.is_file())


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None


__all__ = [
    "expected_operation_ids",
    "list_operation_artifact_ids",
    "list_operation_artifact_refs",
    "load_checkpoint_snapshot_payload",
    "load_completed_replay_tool_calls",
    "planned_tool_call_objects",
    "planned_tool_calls_from_snapshot",
    "turn_output_dir",
    "validate_snapshot_identity",
]
