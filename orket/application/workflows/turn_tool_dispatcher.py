from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from orket.application.middleware import TurnLifecycleInterceptors
from orket.core.policies.tool_gate import ToolGate
from orket.domain.execution import ExecutionTurn
from orket.logging import log_event
from orket.schema import IssueConfig


class ToolDispatcher:
    """Execute tool calls with governance checks and replay caching."""

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
        tool_validation_error_factory: Callable[[list[str]], Exception],
    ) -> None:
        self.tool_gate = tool_gate
        self.middleware = middleware
        self.workspace = workspace
        self.append_memory_event = append_memory_event
        self.hash_payload = hash_payload
        self.load_replay_tool_result = load_replay_tool_result
        self.persist_tool_result = persist_tool_result
        self.tool_validation_error_factory = tool_validation_error_factory

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
        session_id = context.get("session_id", "unknown-session")
        turn_index = int(context.get("turn_index", 0))
        approval_required_tools = {
            str(tool).strip() for tool in (context.get("approval_required_tools") or []) if str(tool).strip()
        }
        request_writer = context.get("create_pending_gate_request")

        for tool_call in turn.tool_calls:
            try:
                binding = self.resolve_skill_tool_binding(context, str(tool_call.tool or ""))
                middleware_outcome = self.middleware.apply_before_tool(
                    tool_call.tool, tool_call.args, issue=issue, role_name=turn.role, context=context
                )
                if middleware_outcome and middleware_outcome.short_circuit:
                    tool_call.result = {
                        "ok": False,
                        "error": middleware_outcome.reason or "tool short-circuited by middleware",
                    }
                    violations.append(tool_call.result["error"])
                    continue
                self.append_memory_event(
                    context,
                    role_name=turn.role,
                    interceptor="before_tool",
                    decision_type="tool_call_ready",
                    tool_calls=[
                        {
                            "tool_name": tool_call.tool,
                            "tool_profile_id": str((binding or {}).get("tool_profile_id") or tool_call.tool or "unknown"),
                            "tool_profile_version": str(context.get("tool_profile_version") or "unknown-v1"),
                            "normalized_args": dict(tool_call.args or {}),
                            "normalization_version": str(context.get("normalization_version") or "json-v1"),
                            "tool_result_fingerprint": self.hash_payload({}),
                            "side_effect_fingerprint": None,
                        }
                    ],
                )

                gate_violation = self.tool_gate.validate(
                    tool_name=tool_call.tool, args=tool_call.args, context=context, roles=roles
                )
                if gate_violation:
                    log_event(
                        "tool_call_blocked",
                        {
                            "issue_id": turn.issue_id,
                            "role": turn.role,
                            "session_id": session_id,
                            "turn_index": turn_index,
                            "tool": tool_call.tool,
                            "args": tool_call.args,
                            "reason": gate_violation,
                        },
                        self.workspace,
                    )
                    violations.append(f"Governance Violation: {gate_violation}")
                    continue

                if bool(context.get("skill_contract_enforced")):
                    if binding is None:
                        violations.append(f"Skill contract violation: undeclared entrypoint/tool '{tool_call.tool}'.")
                        continue
                    missing_permissions = self.missing_required_permissions(binding, context)
                    if missing_permissions:
                        violations.append(
                            "Skill contract violation: missing required permissions for "
                            f"'{tool_call.tool}' ({', '.join(missing_permissions)})."
                        )
                        continue
                    limit_violations = self.runtime_limit_violations(binding, context)
                    if limit_violations:
                        violations.append(
                            "Skill contract violation: runtime limits exceeded for "
                            f"'{tool_call.tool}' ({', '.join(limit_violations)})."
                        )
                        continue

                if tool_call.tool in approval_required_tools:
                    request_id = None
                    if callable(request_writer):
                        maybe_request = request_writer(tool_name=tool_call.tool, tool_args=tool_call.args)
                        if asyncio.iscoroutine(maybe_request):
                            request_id = await maybe_request
                        else:
                            request_id = maybe_request
                    log_event(
                        "tool_approval_required",
                        {
                            "issue_id": turn.issue_id,
                            "role": turn.role,
                            "session_id": session_id,
                            "turn_index": turn_index,
                            "tool": tool_call.tool,
                            "request_id": request_id,
                            "stage_gate_mode": context.get("stage_gate_mode"),
                        },
                        self.workspace,
                    )
                    violations.append(f"Approval required for tool '{tool_call.tool}' before execution.")
                    continue

                log_event(
                    "tool_call_start",
                    {
                        "issue_id": turn.issue_id,
                        "role": turn.role,
                        "session_id": session_id,
                        "turn_index": turn_index,
                        "tool": tool_call.tool,
                        "args": tool_call.args,
                    },
                    self.workspace,
                )
                replay_result = self.load_replay_tool_result(
                    session_id=session_id,
                    issue_id=turn.issue_id,
                    role_name=turn.role,
                    turn_index=turn_index,
                    tool_name=tool_call.tool,
                    tool_args=tool_call.args,
                    resume_mode=bool(context.get("resume_mode")),
                )
                if replay_result is not None:
                    result = replay_result
                    log_event(
                        "tool_call_replayed",
                        {
                            "issue_id": turn.issue_id,
                            "role": turn.role,
                            "session_id": session_id,
                            "turn_index": turn_index,
                            "tool": tool_call.tool,
                        },
                        self.workspace,
                    )
                else:
                    execution_context = dict(context)
                    if isinstance(binding, dict):
                        execution_context["skill_entrypoint_id"] = str(binding.get("entrypoint_id") or "")
                        execution_context["skill_runtime"] = str(binding.get("runtime") or "")
                        execution_context["skill_runtime_version"] = str(binding.get("runtime_version") or "")
                        execution_context["tool_runtime_limits"] = dict(binding.get("runtime_limits") or {})
                    result = await toolbox.execute(tool_call.tool, tool_call.args, execution_context)
                result = self.middleware.apply_after_tool(
                    tool_call.tool, tool_call.args, result, issue=issue, role_name=turn.role, context=context
                )
                tool_call.result = result
                self.append_memory_event(
                    context,
                    role_name=turn.role,
                    interceptor="after_tool",
                    decision_type="tool_call_result",
                    tool_calls=[
                        {
                            "tool_name": tool_call.tool,
                            "tool_profile_id": str((binding or {}).get("tool_profile_id") or tool_call.tool or "unknown"),
                            "tool_profile_version": str(context.get("tool_profile_version") or "unknown-v1"),
                            "normalized_args": dict(tool_call.args or {}),
                            "normalization_version": str(context.get("normalization_version") or "json-v1"),
                            "tool_result_fingerprint": self.hash_payload(result if isinstance(result, dict) else {}),
                            "side_effect_fingerprint": None,
                        }
                    ],
                )
                self.persist_tool_result(
                    session_id=session_id,
                    issue_id=turn.issue_id,
                    role_name=turn.role,
                    turn_index=turn_index,
                    tool_name=tool_call.tool,
                    tool_args=tool_call.args,
                    result=result,
                )
                log_event(
                    "tool_call_result",
                    {
                        "issue_id": turn.issue_id,
                        "role": turn.role,
                        "session_id": session_id,
                        "turn_index": turn_index,
                        "tool": tool_call.tool,
                        "ok": bool(result.get("ok", False)),
                        "error": result.get("error"),
                    },
                    self.workspace,
                )
                if not result.get("ok", False):
                    violations.append(f"Tool {tool_call.tool} failed: {result.get('error')}")
            except (ValueError, TypeError, KeyError, RuntimeError, OSError, AttributeError) as e:
                tool_call.error = str(e)
                log_event(
                    "tool_call_exception",
                    {
                        "issue_id": turn.issue_id,
                        "role": turn.role,
                        "session_id": session_id,
                        "turn_index": turn_index,
                        "tool": tool_call.tool,
                        "error": str(e),
                    },
                    self.workspace,
                )
                violations.append(f"Tool {tool_call.tool} error: {e}")

        if violations:
            raise self.tool_validation_error_factory(violations)

    @staticmethod
    def resolve_skill_tool_binding(context: dict[str, Any], tool_name: str) -> dict[str, Any] | None:
        bindings = context.get("skill_tool_bindings")
        if not isinstance(bindings, dict):
            return None
        binding = bindings.get(str(tool_name).strip())
        if not isinstance(binding, dict):
            return None
        return binding

    def missing_required_permissions(self, binding: dict[str, Any], context: dict[str, Any]) -> list[str]:
        required = binding.get("required_permissions")
        if not isinstance(required, dict) or not required:
            return []
        granted = context.get("granted_permissions")
        granted = granted if isinstance(granted, dict) else {}
        missing: list[str] = []
        for scope, values in required.items():
            required_values = self.permission_values(values)
            granted_values = self.permission_values(granted.get(scope))
            for value in sorted(required_values - granted_values):
                missing.append(f"{scope}:{value}")
        return missing

    @staticmethod
    def permission_values(values: Any) -> set[str]:
        if values is None:
            return set()
        if isinstance(values, str):
            normalized = values.strip()
            return {normalized} if normalized else set()
        if isinstance(values, list):
            return {str(item).strip() for item in values if str(item).strip()}
        return set()

    def runtime_limit_violations(self, binding: dict[str, Any], context: dict[str, Any]) -> list[str]:
        limits = binding.get("runtime_limits")
        if not isinstance(limits, dict) or not limits:
            return []
        violations: list[str] = []
        requested_exec = self.as_positive_float(limits.get("max_execution_time"))
        requested_memory = self.as_positive_float(limits.get("max_memory"))
        allowed_exec = self.as_positive_float(context.get("max_tool_execution_time"))
        allowed_memory = self.as_positive_float(context.get("max_tool_memory"))
        if requested_exec is not None and allowed_exec is not None and requested_exec > allowed_exec:
            violations.append("max_execution_time")
        if requested_memory is not None and allowed_memory is not None and requested_memory > allowed_memory:
            violations.append("max_memory")
        return violations

    @staticmethod
    def as_positive_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None
