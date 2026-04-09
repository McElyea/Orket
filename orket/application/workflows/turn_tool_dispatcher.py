from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneService
from orket.core.domain.execution import ExecutionTurn, ToolCallErrorClass
from orket.core.policies.tool_gate import ToolGate
from orket.logging import log_event
from orket.schema import IssueConfig

from ..services.governed_turn_tool_approval_continuation_service import (
    supports_governed_turn_tool_approval_continuation,
)
from orket.runtime.registry.protocol_hashing import (
    VALIDATOR_VERSION,
    build_step_id,
    default_protocol_hash,
    default_tool_schema_hash,
    derive_operation_id,
    derive_step_seed,
    hash_canonical_json,
)
from .turn_tool_dispatcher_compatibility import resolve_compatibility_translation
from .turn_tool_dispatcher_control_plane import (
    begin_control_plane_execution_if_needed,
    finalize_execution_if_needed,
    persist_non_protocol_tool_result_if_needed,
    publish_preflight_failure_if_needed,
)
from .turn_tool_dispatcher_protocol import (
    collect_protocol_preflight_violations,
    load_or_execute_tool,
    persist_protocol_operation,
)
from .turn_tool_dispatcher_support import (
    as_positive_float,
    build_execution_capsule,
    determinism_violation_details_for_result,
    missing_required_permissions,
    permission_values,
    resolve_skill_tool_binding,
    runtime_limit_violations,
    tool_policy_violation,
)


class ToolDispatcher:
    """Execute tool calls with governance checks and replay/idempotency caching."""

    resolve_skill_tool_binding = staticmethod(resolve_skill_tool_binding)
    missing_required_permissions = staticmethod(missing_required_permissions)
    permission_values = staticmethod(permission_values)
    runtime_limit_violations = staticmethod(runtime_limit_violations)
    as_positive_float = staticmethod(as_positive_float)

    def __init__(
        self,
        *,
        tool_gate: ToolGate,
        middleware: TurnLifecycleInterceptors,
        workspace: Path,
        append_memory_event: Callable[..., None],
        hash_payload: Callable[[Any], str],
        load_replay_tool_result: Callable[..., dict[str, Any] | None],
        persist_tool_result: Callable[..., None],
        load_operation_result: Callable[..., dict[str, Any] | None],
        persist_operation_result: Callable[..., None],
        append_protocol_receipt: Callable[..., dict[str, Any]],
        tool_approval_pending_error_factory: Callable[[str], Exception] | None = None,
        tool_validation_error_factory: Callable[[list[str]], Exception] | None = None,
        control_plane_service: TurnToolControlPlaneService | None = None,
    ) -> None:
        if tool_gate is None:
            raise TypeError("ToolDispatcher requires tool_gate authority before tool execution can begin")
        self.tool_gate = tool_gate
        self.middleware = middleware
        self.workspace = workspace
        self.middleware.bind_workspace(self.workspace)
        self.append_memory_event = append_memory_event
        self.hash_payload = hash_payload
        self.load_replay_tool_result = load_replay_tool_result
        self.persist_tool_result = persist_tool_result
        self.load_operation_result = load_operation_result
        self.persist_operation_result = persist_operation_result
        self.append_protocol_receipt = append_protocol_receipt
        self.tool_approval_pending_error_factory = (
            tool_approval_pending_error_factory or (lambda message: RuntimeError(str(message or "")))
        )
        self.tool_validation_error_factory = (
            tool_validation_error_factory or (lambda violations: RuntimeError(str(list(violations or []))))
        )
        self.control_plane_service = control_plane_service

    async def execute_tools(
        self,
        *,
        turn: ExecutionTurn,
        toolbox: Any,
        context: dict[str, Any],
        issue: IssueConfig | None = None,
    ) -> None:
        violations: list[str] = []
        roles = context.get("roles", [turn.role])
        session_id = str(context.get("session_id", "unknown-session"))
        turn_index = int(context.get("turn_index", 0))
        step_id = build_step_id(issue_id=turn.issue_id, turn_index=turn_index)
        run_seed = str(context.get("run_seed") or session_id)
        step_seed = derive_step_seed(run_seed=run_seed, run_id=session_id, step_id=step_id)
        raw_payload = turn.raw if isinstance(turn.raw, dict) else {}
        proposal_hash = str(raw_payload.get("proposal_hash") or "")
        if not proposal_hash:
            proposal_hash = hash_canonical_json(
                {
                    "content": str(turn.content or ""),
                    "tool_calls": [
                        {
                            "tool": str(call.tool or ""),
                            "args": dict(call.args or {}),
                        }
                        for call in list(turn.tool_calls or [])
                    ],
                }
            )
        validator_version = str(
            raw_payload.get("validator_version") or context.get("validator_version") or VALIDATOR_VERSION
        )
        protocol_hash = str(raw_payload.get("protocol_hash") or context.get("protocol_hash") or default_protocol_hash())
        tool_schema_hash = str(
            raw_payload.get("tool_schema_hash") or context.get("tool_schema_hash") or default_tool_schema_hash()
        )
        protocol_enabled = bool(context.get("protocol_governed_enabled", False))
        protocol_replay_mode = bool(context.get("protocol_replay_mode"))
        control_plane_enabled = not protocol_replay_mode and self.control_plane_service is not None
        if control_plane_enabled and turn.tool_calls:
            tool_names = [str(call.tool or "").strip() for call in turn.tool_calls if str(call.tool or "").strip()]
            # Status-only turns do not produce side-effecting tool evidence, so skip
            # governed turn-tool publication to keep that hot path lightweight.
            if tool_names and all(name == "update_issue_status" for name in tool_names):
                control_plane_enabled = False
        execution_capsule = build_execution_capsule(context)
        approval_required_tools = {
            str(tool).strip() for tool in (context.get("approval_required_tools") or []) if str(tool).strip()
        }
        request_writer = context.get("create_pending_gate_request")
        approval_resolver = context.get("resolve_granted_tool_approval")
        control_plane_run_id: str | None = None
        control_plane_attempt_id: str | None = None
        executed_step_count = 0
        last_result_ref: str | None = None

        if protocol_enabled:
            preflight_violations = await collect_protocol_preflight_violations(
                turn=turn,
                context=context,
                roles=roles,
                approval_required_tools=approval_required_tools,
                tool_gate=self.tool_gate,
                workspace=self.workspace,
                resolve_skill_tool_binding=resolve_skill_tool_binding,
                missing_required_permissions=missing_required_permissions,
                runtime_limit_violations=runtime_limit_violations,
            )
            if preflight_violations:
                await publish_preflight_failure_if_needed(
                    control_plane_enabled=control_plane_enabled,
                    control_plane_service=self.control_plane_service,
                    session_id=session_id,
                    issue_id=turn.issue_id,
                    role_name=turn.role,
                    turn_index=turn_index,
                    proposal_hash=proposal_hash,
                    preflight_violations=preflight_violations,
                )
                if not protocol_replay_mode:
                    first_tool_name = ""
                    if turn.tool_calls:
                        first_tool_name = str(turn.tool_calls[0].tool or "")
                    log_event(
                        "tool_call_exception",
                        {
                            "issue_id": turn.issue_id,
                            "role": turn.role,
                            "session_id": session_id,
                            "turn_index": turn_index,
                            "tool": first_tool_name,
                            "error": str(preflight_violations[0]),
                        },
                        self.workspace,
                    )
                raise self.tool_validation_error_factory(preflight_violations)
        control_plane_run_id, control_plane_attempt_id = await begin_control_plane_execution_if_needed(
            control_plane_enabled=control_plane_enabled,
            control_plane_service=self.control_plane_service,
            has_tool_calls=bool(turn.tool_calls),
            session_id=session_id,
            issue_id=turn.issue_id,
            role_name=turn.role,
            turn_index=turn_index,
            proposal_hash=proposal_hash,
            resume_mode=bool(context.get("resume_mode")),
        )

        for index, tool_call in enumerate(turn.tool_calls):
            operation_id = derive_operation_id(
                run_id=session_id,
                step_id=step_id,
                tool_index=index,
            )
            receipt_seq = index + 1
            tool_name = str(tool_call.tool or "")
            binding = resolve_skill_tool_binding(context, tool_name)
            try:
                middleware_outcome = self.middleware.apply_before_tool(
                    tool_name,
                    tool_call.args,
                    issue=issue,
                    role_name=turn.role,
                    context=context,
                )
                if middleware_outcome and middleware_outcome.short_circuit:
                    reason = middleware_outcome.reason or "tool short-circuited by middleware"
                    tool_call.result = {
                        "ok": False,
                        "error": reason,
                    }
                    tool_call.error = reason
                    tool_call.error_class = (
                        ToolCallErrorClass.INTERCEPTOR_CRASH
                        if reason == "interceptor_crash"
                        else ToolCallErrorClass.GATE_BLOCKED
                    )
                    violations.append(reason)
                    continue

                if not protocol_replay_mode:
                    self.append_memory_event(
                        context,
                        role_name=turn.role,
                        interceptor="before_tool",
                        decision_type="tool_call_ready",
                        tool_calls=[
                            {
                                "tool_name": tool_name,
                                "tool_profile_id": str(
                                    (binding or {}).get("tool_profile_id") or tool_name or "unknown"
                                ),
                                "tool_profile_version": str(context.get("tool_profile_version") or "unknown-v1"),
                                "normalized_args": dict(tool_call.args or {}),
                                "normalization_version": str(context.get("normalization_version") or "json-v1"),
                                "tool_result_fingerprint": self.hash_payload({}),
                                "side_effect_fingerprint": None,
                            }
                        ],
                    )

                gate_violation = await self.tool_gate.validate(
                    tool_name=tool_name,
                    args=tool_call.args,
                    context=context,
                    roles=roles,
                )
                policy_violation = tool_policy_violation(
                    tool_name=tool_name,
                    binding=binding,
                    context=context,
                    issue_id=turn.issue_id,
                )
                if policy_violation:
                    tool_call.error = policy_violation
                    tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
                    if not protocol_replay_mode:
                        log_event(
                            "tool_call_blocked",
                            {
                                "issue_id": turn.issue_id,
                                "role": turn.role,
                                "session_id": session_id,
                                "turn_index": turn_index,
                                "tool": tool_name,
                                "args": tool_call.args,
                                "reason": policy_violation,
                            },
                            self.workspace,
                        )
                    violations.append(policy_violation)
                    continue
                if gate_violation:
                    tool_call.error = str(gate_violation)
                    tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
                    if not protocol_replay_mode:
                        log_event(
                            "tool_call_blocked",
                            {
                                "issue_id": turn.issue_id,
                                "role": turn.role,
                                "session_id": session_id,
                                "turn_index": turn_index,
                                "tool": tool_name,
                                "args": tool_call.args,
                                "reason": gate_violation,
                            },
                            self.workspace,
                        )
                    violations.append(f"Governance Violation: {gate_violation}")
                    continue

                if bool(context.get("skill_contract_enforced")):
                    if binding is None:
                        tool_call.error = f"Skill contract violation: undeclared entrypoint/tool '{tool_name}'."
                        tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
                        violations.append(f"Skill contract violation: undeclared entrypoint/tool '{tool_name}'.")
                        continue
                    missing_permissions = missing_required_permissions(binding, context)
                    if missing_permissions:
                        tool_call.error = (
                            "Skill contract violation: missing required permissions for "
                            f"'{tool_name}' ({', '.join(missing_permissions)})."
                        )
                        tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
                        violations.append(tool_call.error)
                        continue
                    limit_violations = runtime_limit_violations(binding, context)
                    if limit_violations:
                        tool_call.error = (
                            "Skill contract violation: runtime limits exceeded for "
                            f"'{tool_name}' ({', '.join(limit_violations)})."
                        )
                        tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
                        violations.append(tool_call.error)
                        continue

                if tool_name in approval_required_tools:
                    admitted_continuation_slice = supports_governed_turn_tool_approval_continuation(
                        tool_name=tool_name,
                        context=context,
                        issue_id=turn.issue_id,
                    )
                    granted_request_id = None
                    if admitted_continuation_slice and callable(approval_resolver):
                        maybe_request = approval_resolver(tool_name=tool_name, tool_args=dict(tool_call.args or {}))
                        if asyncio.iscoroutine(maybe_request):
                            granted_request_id = await maybe_request
                        else:
                            granted_request_id = maybe_request
                    if admitted_continuation_slice and granted_request_id:
                        if not protocol_replay_mode:
                            log_event(
                                "tool_approval_granted",
                                {
                                    "issue_id": turn.issue_id,
                                    "role": turn.role,
                                    "session_id": session_id,
                                    "turn_index": turn_index,
                                    "tool": tool_name,
                                    "request_id": str(granted_request_id),
                                    "stage_gate_mode": context.get("stage_gate_mode"),
                                },
                                self.workspace,
                            )
                    else:
                        request_id = None
                        if callable(request_writer):
                            maybe_request = request_writer(tool_name=tool_name, tool_args=tool_call.args)
                            if asyncio.iscoroutine(maybe_request):
                                request_id = await maybe_request
                            else:
                                request_id = maybe_request
                        message = f"Approval required for tool '{tool_name}' before execution."
                        if not protocol_replay_mode:
                            log_event(
                                "tool_approval_required",
                                {
                                    "issue_id": turn.issue_id,
                                    "role": turn.role,
                                    "session_id": session_id,
                                    "turn_index": turn_index,
                                    "tool": tool_name,
                                    "request_id": request_id,
                                    "stage_gate_mode": context.get("stage_gate_mode"),
                                },
                                self.workspace,
                            )
                        if admitted_continuation_slice:
                            raise self.tool_approval_pending_error_factory(message)
                        tool_call.error = message
                        tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
                        violations.append(message)
                        continue

                compatibility_translation, compatibility_violation = resolve_compatibility_translation(
                    tool_name=tool_name,
                    tool_args=dict(tool_call.args or {}),
                    binding=binding,
                    context=context,
                )
                if compatibility_violation:
                    tool_call.error = compatibility_violation
                    tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
                    violations.append(compatibility_violation)
                    continue

                if not protocol_replay_mode:
                    log_event(
                        "tool_call_start",
                        {
                            "issue_id": turn.issue_id,
                            "role": turn.role,
                            "session_id": session_id,
                            "turn_index": turn_index,
                            "tool": tool_name,
                            "args": tool_call.args,
                            "operation_id": operation_id,
                        },
                        self.workspace,
                    )

                result, replayed = await load_or_execute_tool(
                    protocol_enabled=protocol_enabled,
                    session_id=session_id,
                    turn=turn,
                    tool_name=tool_name,
                    tool_args=dict(tool_call.args or {}),
                    turn_index=turn_index,
                    operation_id=operation_id,
                    binding=binding,
                    toolbox=toolbox,
                    context=context,
                    step_id=step_id,
                    step_seed=step_seed,
                    validator_version=validator_version,
                    protocol_hash=protocol_hash,
                    tool_schema_hash=tool_schema_hash,
                    compatibility_translation=compatibility_translation,
                    load_operation_result=self.load_operation_result,
                    load_replay_tool_result=self.load_replay_tool_result,
                )

                result = self.middleware.apply_after_tool(
                    tool_name,
                    tool_call.args,
                    result,
                    issue=issue,
                    role_name=turn.role,
                    context=context,
                )
                if not isinstance(result, dict):
                    raw_type = type(result).__name__
                    if not protocol_replay_mode:
                        log_event(
                            "tool_result_invalid",
                            {
                                "issue_id": turn.issue_id,
                                "role": turn.role,
                                "session_id": session_id,
                                "turn_index": turn_index,
                                "tool": tool_name,
                                "operation_id": operation_id,
                                "result_type": raw_type,
                            },
                            self.workspace,
                        )
                    result = {
                        "ok": False,
                        "error": f"tool middleware returned non-dict result ({raw_type})",
                    }
                determinism_violation = determinism_violation_details_for_result(
                    tool_name=tool_name,
                    binding=binding,
                    result=result,
                )
                if determinism_violation:
                    if not protocol_replay_mode:
                        log_event(
                            "determinism_violation",
                            {
                                "issue_id": turn.issue_id,
                                "role": turn.role,
                                "session_id": session_id,
                                "turn_index": turn_index,
                                "tool": tool_name,
                                "operation_id": operation_id,
                                "error": determinism_violation["error"],
                                "error_code": determinism_violation["error_code"],
                                "determinism_class": determinism_violation["determinism_class"],
                                "capability_profile": determinism_violation["capability_profile"],
                                "tool_contract_version": determinism_violation["tool_contract_version"],
                                "side_effect_signal_keys": list(determinism_violation["side_effect_signal_keys"]),
                            },
                            self.workspace,
                        )
                    result = {
                        "ok": False,
                        "error": determinism_violation["error"],
                        "error_code": determinism_violation["error_code"],
                        "determinism_class": determinism_violation["determinism_class"],
                        "capability_profile": determinism_violation["capability_profile"],
                        "tool_contract_version": determinism_violation["tool_contract_version"],
                        "side_effect_signal_keys": list(determinism_violation["side_effect_signal_keys"]),
                    }
                tool_call.result = result
                if not protocol_replay_mode:
                    self.append_memory_event(
                        context,
                        role_name=turn.role,
                        interceptor="after_tool",
                        decision_type="tool_call_result",
                        tool_calls=[
                            {
                                "tool_name": tool_name,
                                "tool_profile_id": str(
                                    (binding or {}).get("tool_profile_id") or tool_name or "unknown"
                                ),
                                "tool_profile_version": str(context.get("tool_profile_version") or "unknown-v1"),
                                "normalized_args": dict(tool_call.args or {}),
                                "normalization_version": str(context.get("normalization_version") or "json-v1"),
                                "tool_result_fingerprint": self.hash_payload(
                                    result if isinstance(result, dict) else {}
                                ),
                                "side_effect_fingerprint": None,
                            }
                        ],
                    )

                result_ref: str | None = None
                if protocol_enabled:
                    if not protocol_replay_mode:
                        result_ref = await persist_protocol_operation(
                            session_id=session_id,
                            issue_id=turn.issue_id,
                            role_name=turn.role,
                            turn_index=turn_index,
                            index=index,
                            step_id=step_id,
                            receipt_seq=receipt_seq,
                            proposal_hash=proposal_hash,
                            validator_version=validator_version,
                            protocol_hash=protocol_hash,
                            tool_schema_hash=tool_schema_hash,
                            execution_capsule=execution_capsule,
                            context=context,
                            tool_name=tool_name,
                            tool_args=dict(tool_call.args or {}),
                            result=result,
                            binding=binding,
                            operation_id=operation_id,
                            replayed=bool(replayed),
                            persist_operation_result=self.persist_operation_result,
                            append_protocol_receipt=self.append_protocol_receipt,
                            control_plane_enabled=control_plane_enabled,
                            control_plane_service=self.control_plane_service,
                            control_plane_run_id=control_plane_run_id,
                            control_plane_attempt_id=control_plane_attempt_id,
                            retry_count=int(context.get("retry_count", 0) or 0),
                            validator_duration_ms=int(context.get("validator_duration_ms", 0) or 0),
                        )
                elif not protocol_replay_mode:
                    result_ref = await persist_non_protocol_tool_result_if_needed(
                        persist_tool_result=self.persist_tool_result, persist_operation_result=self.persist_operation_result,
                        session_id=session_id,
                        issue_id=turn.issue_id,
                        role_name=turn.role,
                        turn_index=turn_index,
                        tool_name=tool_name,
                        tool_args=dict(tool_call.args or {}),
                        result=result,
                        control_plane_enabled=control_plane_enabled,
                        control_plane_service=self.control_plane_service,
                        control_plane_run_id=control_plane_run_id,
                        control_plane_attempt_id=control_plane_attempt_id,
                        binding=binding,
                        operation_id=operation_id,
                        replayed=bool(replayed),
                    )
                if result_ref is not None:
                    executed_step_count += 1
                    last_result_ref = result_ref

                if not protocol_replay_mode:
                    log_event(
                        "tool_call_result",
                        {
                            "issue_id": turn.issue_id,
                            "role": turn.role,
                            "session_id": session_id,
                            "turn_index": turn_index,
                            "tool": tool_name,
                            "ok": bool(result.get("ok", False)),
                            "error": result.get("error"),
                            "operation_id": operation_id,
                            "replayed": bool(replayed),
                        },
                        self.workspace,
                    )
                if not result.get("ok", False):
                    tool_call.error = str(result.get("error") or "tool execution failed")
                    tool_call.error_class = ToolCallErrorClass.EXECUTION_FAILED
                    violations.append(f"Tool {tool_name} failed: {result.get('error')}")
            except (ValueError, TypeError, KeyError, RuntimeError, OSError, AttributeError) as exc:
                tool_call.error = str(exc)
                tool_call.error_class = ToolCallErrorClass.EXECUTION_FAILED
                if not protocol_replay_mode:
                    log_event(
                        "tool_call_exception",
                        {
                            "issue_id": turn.issue_id,
                            "role": turn.role,
                            "session_id": session_id,
                            "turn_index": turn_index,
                            "tool": tool_name,
                            "error": str(exc),
                            "operation_id": operation_id,
                        },
                        self.workspace,
                    )
                violations.append(f"Tool {tool_name} error: {exc}")

        if violations:
            await finalize_execution_if_needed(
                control_plane_enabled=control_plane_enabled,
                control_plane_service=self.control_plane_service,
                control_plane_run_id=control_plane_run_id,
                control_plane_attempt_id=control_plane_attempt_id,
                authoritative_result_ref=last_result_ref or f"turn-tool-violations:{control_plane_run_id}",
                violation_reasons=violations,
                executed_step_count=executed_step_count,
            )
            raise self.tool_validation_error_factory(violations)
        await finalize_execution_if_needed(
            control_plane_enabled=control_plane_enabled,
            control_plane_service=self.control_plane_service,
            control_plane_run_id=control_plane_run_id,
            control_plane_attempt_id=control_plane_attempt_id,
            authoritative_result_ref=last_result_ref or f"turn-tool-complete:{control_plane_run_id}",
            violation_reasons=[],
            executed_step_count=executed_step_count,
        )
