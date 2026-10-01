"""Tool result observation and publication at the dispatch phase boundaries."""
from __future__ import annotations

from functools import partial
from typing import Any

from orket.core.domain.execution import ToolCallErrorClass
from orket.logging import log_event

from .turn_tool_dispatch_context import DispatchRun, DispatchStep
from .turn_tool_dispatcher_control_plane import prepare_dispatch_if_needed
from .turn_tool_dispatcher_protocol import load_or_execute_tool
from .turn_tool_dispatcher_support import determinism_violation_details_for_result
from .turn_tool_result_persistence import persist_non_protocol_tool_result_if_needed, persist_protocol_operation


async def invoke_tool(
    run: DispatchRun, step: DispatchStep, compatibility_translation: dict[str, Any] | None
) -> tuple[dict[str, Any], bool, bool]:
    if not run.protocol_replay_mode:
        log_event(
            "tool_call_start",
            {
                "issue_id": run.turn.issue_id,
                "role": run.turn.role,
                "session_id": run.session_id,
                "turn_index": run.turn_index,
                "tool": step.tool_name,
                "args": step.tool_call.args,
                "operation_id": step.operation_id,
            },
            run.workspace,
        )
    result, replayed, operation_record_present = await load_or_execute_tool(
        protocol_enabled=run.protocol_enabled,
        control_plane_enabled=run.control_plane_enabled,
        destination=run.destination,
        turn=run.turn,
        tool_name=step.tool_name,
        tool_args=dict(step.tool_call.args or {}),
        operation_id=step.operation_id,
        binding=step.binding,
        toolbox=run.toolbox,
        context=run.context,
        step_id=run.step_id,
        step_seed=run.step_seed,
        validator_version=run.validator_version,
        protocol_hash=run.protocol_hash,
        tool_schema_hash=run.tool_schema_hash,
        compatibility_translation=compatibility_translation,
        load_operation_result=run.owner.load_operation_result,
        load_replay_tool_result=run.owner.load_replay_tool_result,
        prepare_dispatch=partial(
            prepare_dispatch_if_needed,
            namespace_scope=run.control_plane.namespace_scope,
            control_plane_enabled=run.control_plane_enabled,
            control_plane_service=run.control_plane_service,
            control_plane_run_id=run.control_plane_run_id,
            control_plane_attempt_id=run.control_plane_attempt_id,
        ),
    )
    return (result, replayed, operation_record_present)


def observe_tool_result(run: DispatchRun, step: DispatchStep, result: dict[str, Any], replayed: bool) -> dict[str, Any]:
    result = run.owner.middleware.apply_after_tool(
        step.tool_name,
        step.tool_call.args,
        result,
        replayed=replayed,
        issue=run.issue,
        role_name=run.turn.role,
        context=run.context,
    )
    if not isinstance(result, dict):
        raw_type = type(result).__name__
        if not run.protocol_replay_mode:
            log_event(
                "tool_result_invalid",
                {
                    "issue_id": run.turn.issue_id,
                    "role": run.turn.role,
                    "session_id": run.session_id,
                    "turn_index": run.turn_index,
                    "tool": step.tool_name,
                    "operation_id": step.operation_id,
                    "result_type": raw_type,
                },
                run.workspace,
            )
        result = {"ok": False, "error": f"tool middleware returned non-dict result ({raw_type})"}
    result = _apply_result_determinism(run, step, result, replayed)
    step.tool_call.result = result
    if not run.protocol_replay_mode:
        run.owner.append_memory_event(
            run.memory_events,
            role_name=run.turn.role,
            interceptor="after_tool",
            decision_type="tool_call_result",
            tool_calls=[
                {
                    "tool_name": step.tool_name,
                    "tool_profile_id": str((step.binding or {}).get("tool_profile_id") or step.tool_name or "unknown"),
                    "tool_profile_version": run.memory_inputs.event_tool_profile_version,
                    "normalized_args": dict(step.tool_call.args or {}),
                    "normalization_version": run.memory_inputs.event_normalization_version,
                    "tool_result_fingerprint": run.owner.hash_payload(result if isinstance(result, dict) else {}),
                    "side_effect_fingerprint": None,
                }
            ],
        )
    return result


async def publish_tool_result(
    run: DispatchRun, step: DispatchStep, result: dict[str, Any], replayed: bool, operation_record_present: bool
) -> None:
    result_ref: str | None = None
    if run.protocol_enabled:
        if not run.protocol_replay_mode:
            result_ref = await persist_protocol_operation(
                destination=run.destination,
                index=step.index,
                step_id=run.step_id,
                receipt_seq=step.receipt_seq,
                proposal_hash=run.proposal_hash,
                validator_version=run.validator_version,
                protocol_hash=run.protocol_hash,
                tool_schema_hash=run.tool_schema_hash,
                execution_capsule=run.execution_capsule,
                context=run.context,
                tool_name=step.tool_name,
                tool_args=dict(step.tool_call.args or {}),
                result=result,
                binding=step.binding,
                operation_id=step.operation_id,
                replayed=bool(replayed),
                operation_record_present=operation_record_present,
                persist_operation_result=run.owner.persist_operation_result,
                append_protocol_receipt=run.owner.append_protocol_receipt,
                control_plane_enabled=run.control_plane_enabled,
                control_plane_service=run.control_plane_service,
                control_plane_run_id=run.control_plane_run_id,
                control_plane_attempt_id=run.control_plane_attempt_id,
                retry_count=int(run.context.get("retry_count", 0) or 0),
            )
    elif not run.protocol_replay_mode:
        result_ref = await persist_non_protocol_tool_result_if_needed(
            persist_tool_result=run.owner.persist_tool_result,
            persist_operation_result=run.owner.persist_operation_result,
            destination=run.destination,
            tool_name=step.tool_name,
            tool_args=dict(step.tool_call.args or {}),
            result=result,
            control_plane_enabled=run.control_plane_enabled,
            control_plane_service=run.control_plane_service,
            control_plane_run_id=run.control_plane_run_id,
            control_plane_attempt_id=run.control_plane_attempt_id,
            binding=step.binding,
            operation_id=step.operation_id,
            replayed=bool(replayed),
            operation_record_present=operation_record_present,
        )
    if result_ref is not None:
        run.executed_step_count += 1
        run.last_result_ref = result_ref


def record_tool_outcome(run: DispatchRun, step: DispatchStep, result: dict[str, Any], replayed: bool) -> None:
    if not run.protocol_replay_mode:
        log_event(
            "tool_call_result",
            {
                "issue_id": run.turn.issue_id,
                "role": run.turn.role,
                "session_id": run.session_id,
                "turn_index": run.turn_index,
                "tool": step.tool_name,
                "ok": bool(result.get("ok", False)),
                "error": result.get("error"),
                "operation_id": step.operation_id,
                "replayed": bool(replayed),
            },
            run.workspace,
        )
    if not result.get("ok", False):
        step.tool_call.error = str(result.get("error") or "tool execution failed")
        step.tool_call.error_class = ToolCallErrorClass.EXECUTION_FAILED
        run.violations.append(f"Tool {step.tool_name} failed: {result.get('error')}")


def record_tool_failure(run: DispatchRun, step: DispatchStep, exc: Exception) -> None:
    step.tool_call.error = str(exc)
    step.tool_call.error_class = ToolCallErrorClass.EXECUTION_FAILED
    if not run.protocol_replay_mode:
        log_event(
            "tool_call_exception",
            {
                "issue_id": run.turn.issue_id,
                "role": run.turn.role,
                "session_id": run.session_id,
                "turn_index": run.turn_index,
                "tool": step.tool_name,
                "error": str(exc),
                "operation_id": step.operation_id,
            },
            run.workspace,
        )
    run.violations.append(f"Tool {step.tool_name} error: {exc}")


def _apply_result_determinism(
    run: DispatchRun, step: DispatchStep, result: dict[str, Any], replayed: bool
) -> dict[str, Any]:
    determinism_violation = determinism_violation_details_for_result(
        tool_name=step.tool_name, binding=step.binding, result=result
    )
    if determinism_violation:
        if not run.protocol_replay_mode:
            log_event(
                "determinism_violation",
                {
                    "issue_id": run.turn.issue_id,
                    "role": run.turn.role,
                    "session_id": run.session_id,
                    "turn_index": run.turn_index,
                    "tool": step.tool_name,
                    "operation_id": step.operation_id,
                    "error": determinism_violation["error"],
                    "error_code": determinism_violation["error_code"],
                    "determinism_class": determinism_violation["determinism_class"],
                    "capability_profile": determinism_violation["capability_profile"],
                    "tool_contract_version": determinism_violation["tool_contract_version"],
                    "side_effect_signal_keys": list(determinism_violation["side_effect_signal_keys"]),
                },
                run.workspace,
            )
        if replayed:
            raise ValueError(determinism_violation["error"])
        result = {
            "ok": False,
            "error": determinism_violation["error"],
            "error_code": determinism_violation["error_code"],
            "determinism_class": determinism_violation["determinism_class"],
            "capability_profile": determinism_violation["capability_profile"],
            "tool_contract_version": determinism_violation["tool_contract_version"],
            "side_effect_signal_keys": list(determinism_violation["side_effect_signal_keys"]),
        }
    return result
