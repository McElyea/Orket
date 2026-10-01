"""Existing dispatch preflight, gates and operator approval in their original order."""
from __future__ import annotations

import asyncio

from orket.core.domain.execution import ToolCallErrorClass
from orket.logging import log_event

from ..services.governed_turn_tool_approval_continuation_service import (
    supports_governed_turn_tool_approval_continuation,
)
from .turn_tool_dispatch_context import DispatchRun, DispatchStep
from .turn_tool_dispatcher_control_plane import (
    begin_control_plane_execution_if_needed,
    publish_preflight_failure_if_needed,
)
from .turn_tool_dispatcher_protocol import collect_protocol_preflight_violations
from .turn_tool_dispatcher_support import (
    missing_required_permissions,
    resolve_skill_tool_binding,
    runtime_limit_violations,
    tool_policy_violation,
)


async def prepare_dispatch_run(run: DispatchRun) -> None:
    if run.protocol_enabled:
        preflight_violations = await collect_protocol_preflight_violations(
            turn=run.turn,
            context=run.context,
            roles=run.roles,
            approval_required_tools=run.approval_required_tools,
            tool_gate=run.owner.tool_gate,
            workspace=run.workspace,
            resolve_skill_tool_binding=resolve_skill_tool_binding,
            missing_required_permissions=missing_required_permissions,
            runtime_limit_violations=runtime_limit_violations,
        )
        if preflight_violations:
            await publish_preflight_failure_if_needed(
                control_plane_enabled=run.control_plane_enabled,
                control_plane_service=run.control_plane_service,
                session_id=run.session_id,
                issue_id=run.turn.issue_id,
                role_name=run.turn.role,
                turn_index=run.turn_index,
                proposal_hash=run.proposal_hash,
                preflight_violations=preflight_violations,
            )
            if not run.protocol_replay_mode:
                first_tool_name = ""
                if run.turn.tool_calls:
                    first_tool_name = str(run.turn.tool_calls[0].tool or "")
                log_event(
                    "tool_call_exception",
                    {
                        "issue_id": run.turn.issue_id,
                        "role": run.turn.role,
                        "session_id": run.session_id,
                        "turn_index": run.turn_index,
                        "tool": first_tool_name,
                        "error": str(preflight_violations[0]),
                    },
                    run.workspace,
                )
            raise run.owner.tool_validation_error_factory(preflight_violations)
    run.control_plane_run_id, run.control_plane_attempt_id = await begin_control_plane_execution_if_needed(
        control_plane_enabled=run.control_plane_enabled,
        control_plane_service=run.control_plane_service,
        has_tool_calls=bool(run.turn.tool_calls),
        session_id=run.session_id,
        issue_id=run.turn.issue_id,
        role_name=run.turn.role,
        turn_index=run.turn_index,
        proposal_hash=run.proposal_hash,
        resume_mode=bool(run.context.get("resume_mode")),
    )


def before_tool(run: DispatchRun, step: DispatchStep) -> bool:
    middleware_outcome = run.owner.middleware.apply_before_tool(
        step.tool_name, step.tool_call.args, issue=run.issue, role_name=run.turn.role, context=run.context
    )
    if middleware_outcome and middleware_outcome.short_circuit:
        reason = middleware_outcome.reason or "tool short-circuited by middleware"
        step.tool_call.result = {"ok": False, "error": reason}
        step.tool_call.error = reason
        step.tool_call.error_class = (
            ToolCallErrorClass.INTERCEPTOR_CRASH if reason == "interceptor_crash" else ToolCallErrorClass.GATE_BLOCKED
        )
        run.violations.append(reason)
        return False
    if not run.protocol_replay_mode:
        run.owner.append_memory_event(
            run.memory_events,
            role_name=run.turn.role,
            interceptor="before_tool",
            decision_type="tool_call_ready",
            tool_calls=[
                {
                    "tool_name": step.tool_name,
                    "tool_profile_id": str((step.binding or {}).get("tool_profile_id") or step.tool_name or "unknown"),
                    "tool_profile_version": run.memory_inputs.event_tool_profile_version,
                    "normalized_args": dict(step.tool_call.args or {}),
                    "normalization_version": run.memory_inputs.event_normalization_version,
                    "tool_result_fingerprint": run.owner.hash_payload({}),
                    "side_effect_fingerprint": None,
                }
            ],
        )
    return True


async def validate_tool(run: DispatchRun, step: DispatchStep) -> bool:
    gate_violation = await run.owner.tool_gate.validate(
        tool_name=step.tool_name, args=step.tool_call.args, context=run.context, roles=run.roles
    )
    policy_violation = tool_policy_violation(
        tool_name=step.tool_name, binding=step.binding, context=run.context, issue_id=run.turn.issue_id
    )
    if policy_violation:
        step.tool_call.error = policy_violation
        step.tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
        if not run.protocol_replay_mode:
            log_event(
                "tool_call_blocked",
                {
                    "issue_id": run.turn.issue_id,
                    "role": run.turn.role,
                    "session_id": run.session_id,
                    "turn_index": run.turn_index,
                    "tool": step.tool_name,
                    "args": step.tool_call.args,
                    "reason": policy_violation,
                },
                run.workspace,
            )
        run.violations.append(policy_violation)
        return False
    if gate_violation:
        step.tool_call.error = str(gate_violation)
        step.tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
        if not run.protocol_replay_mode:
            log_event(
                "tool_call_blocked",
                {
                    "issue_id": run.turn.issue_id,
                    "role": run.turn.role,
                    "session_id": run.session_id,
                    "turn_index": run.turn_index,
                    "tool": step.tool_name,
                    "args": step.tool_call.args,
                    "reason": gate_violation,
                },
                run.workspace,
            )
        run.violations.append(f"Governance Violation: {gate_violation}")
        return False
    if bool(run.context.get("skill_contract_enforced")):
        if step.binding is None:
            step.tool_call.error = f"Skill contract violation: undeclared entrypoint/tool '{step.tool_name}'."
            step.tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
            run.violations.append(f"Skill contract violation: undeclared entrypoint/tool '{step.tool_name}'.")
            return False
        missing_permissions = missing_required_permissions(step.binding, run.context)
        if missing_permissions:
            step.tool_call.error = f"Skill contract violation: missing required permissions for '{step.tool_name}' ({', '.join(missing_permissions)})."
            step.tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
            run.violations.append(step.tool_call.error)
            return False
        limit_violations = runtime_limit_violations(step.binding, run.context)
        if limit_violations:
            step.tool_call.error = f"Skill contract violation: runtime limits exceeded for '{step.tool_name}' ({', '.join(limit_violations)})."
            step.tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
            run.violations.append(step.tool_call.error)
            return False
    return True


async def approve_tool(run: DispatchRun, step: DispatchStep) -> bool:
    if step.tool_name in run.approval_required_tools:
        admitted_continuation_slice = supports_governed_turn_tool_approval_continuation(
            tool_name=step.tool_name, context=run.context, issue_id=run.turn.issue_id
        )
        granted_request_id = None
        if admitted_continuation_slice and callable(run.approval_resolver):
            maybe_request = run.approval_resolver(
                destination=run.destination, tool_name=step.tool_name, tool_args=dict(step.tool_call.args or {})
            )
            if asyncio.iscoroutine(maybe_request):
                granted_request_id = await maybe_request
            else:
                granted_request_id = maybe_request
        if admitted_continuation_slice and granted_request_id:
            if not run.protocol_replay_mode:
                log_event(
                    "tool_approval_granted",
                    {
                        "issue_id": run.turn.issue_id,
                        "role": run.turn.role,
                        "session_id": run.session_id,
                        "turn_index": run.turn_index,
                        "tool": step.tool_name,
                        "request_id": str(granted_request_id),
                        "stage_gate_mode": run.context.get("stage_gate_mode"),
                    },
                    run.workspace,
                )
        else:
            request_id = None
            if callable(run.request_writer):
                maybe_request = run.request_writer(
                    destination=run.destination, tool_name=step.tool_name, tool_args=step.tool_call.args
                )
                if asyncio.iscoroutine(maybe_request):
                    request_id = await maybe_request
                else:
                    request_id = maybe_request
            message = f"Approval required for tool '{step.tool_name}' before execution."
            if not run.protocol_replay_mode:
                log_event(
                    "tool_approval_required",
                    {
                        "issue_id": run.turn.issue_id,
                        "role": run.turn.role,
                        "session_id": run.session_id,
                        "turn_index": run.turn_index,
                        "tool": step.tool_name,
                        "request_id": request_id,
                        "stage_gate_mode": run.context.get("stage_gate_mode"),
                    },
                    run.workspace,
                )
            if admitted_continuation_slice:
                raise run.owner.tool_approval_pending_error_factory(message)
            step.tool_call.error = message
            step.tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
            run.violations.append(message)
            return False
    return True
