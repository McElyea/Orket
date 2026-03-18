from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from orket.application.middleware import TurnLifecycleInterceptors
from orket.core.policies.tool_gate import ToolGate
from orket.domain.execution import ExecutionTurn
from orket.logging import log_event
from orket.schema import IssueConfig

from .protocol_hashing import (
    VALIDATOR_VERSION,
    build_step_id,
    default_protocol_hash,
    default_tool_schema_hash,
    derive_operation_id,
    derive_step_seed,
    hash_canonical_json,
)
from .tool_invocation_contracts import (
    build_tool_invocation_manifest,
    compute_tool_call_hash,
)
from .turn_tool_dispatcher_compatibility import resolve_compatibility_translation
from .turn_tool_dispatcher_protocol import (
    collect_protocol_preflight_violations,
    load_or_execute_tool,
)
from .turn_tool_dispatcher_support import (
    as_positive_float,
    build_execution_capsule,
    determinism_violation_for_result,
    missing_required_permissions,
    permission_values,
    resolve_skill_tool_binding,
    runtime_limit_violations,
)


class ToolDispatcher:
    """Execute tool calls with governance checks and replay/idempotency caching."""

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
        tool_validation_error_factory: Callable[[list[str]], Exception],
    ) -> None:
        self.tool_gate = tool_gate
        self.middleware = middleware
        self.workspace = workspace
        self.append_memory_event = append_memory_event
        self.hash_payload = hash_payload
        self.load_replay_tool_result = load_replay_tool_result
        self.persist_tool_result = persist_tool_result
        self.load_operation_result = load_operation_result
        self.persist_operation_result = persist_operation_result
        self.append_protocol_receipt = append_protocol_receipt
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
        execution_capsule = build_execution_capsule(context)
        approval_required_tools = {
            str(tool).strip() for tool in (context.get("approval_required_tools") or []) if str(tool).strip()
        }
        request_writer = context.get("create_pending_gate_request")

        if protocol_enabled:
            preflight_violations = self.collect_protocol_preflight_violations(
                turn=turn,
                context=context,
                roles=roles,
                approval_required_tools=approval_required_tools,
            )
            if preflight_violations:
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

        for index, tool_call in enumerate(turn.tool_calls):
            operation_id = derive_operation_id(
                run_id=session_id,
                step_id=step_id,
                tool_index=index,
            )
            receipt_seq = index + 1
            tool_name = str(tool_call.tool or "")
            binding = self.resolve_skill_tool_binding(context, tool_name)
            try:
                middleware_outcome = self.middleware.apply_before_tool(
                    tool_name,
                    tool_call.args,
                    issue=issue,
                    role_name=turn.role,
                    context=context,
                )
                if middleware_outcome and middleware_outcome.short_circuit:
                    tool_call.result = {
                        "ok": False,
                        "error": middleware_outcome.reason or "tool short-circuited by middleware",
                    }
                    violations.append(tool_call.result["error"])
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

                gate_violation = self.tool_gate.validate(
                    tool_name=tool_name,
                    args=tool_call.args,
                    context=context,
                    roles=roles,
                )
                if gate_violation:
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
                        violations.append(f"Skill contract violation: undeclared entrypoint/tool '{tool_name}'.")
                        continue
                    missing_permissions = self.missing_required_permissions(binding, context)
                    if missing_permissions:
                        violations.append(
                            "Skill contract violation: missing required permissions for "
                            f"'{tool_name}' ({', '.join(missing_permissions)})."
                        )
                        continue
                    limit_violations = self.runtime_limit_violations(binding, context)
                    if limit_violations:
                        violations.append(
                            "Skill contract violation: runtime limits exceeded for "
                            f"'{tool_name}' ({', '.join(limit_violations)})."
                        )
                        continue

                if tool_name in approval_required_tools:
                    request_id = None
                    if callable(request_writer):
                        maybe_request = request_writer(tool_name=tool_name, tool_args=tool_call.args)
                        if asyncio.iscoroutine(maybe_request):
                            request_id = await maybe_request
                        else:
                            request_id = maybe_request
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
                    violations.append(f"Approval required for tool '{tool_name}' before execution.")
                    continue

                compatibility_translation, compatibility_violation = resolve_compatibility_translation(
                    tool_name=tool_name,
                    tool_args=dict(tool_call.args or {}),
                    binding=binding,
                    context=context,
                )
                if compatibility_violation:
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
                determinism_violation = determinism_violation_for_result(
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
                                "error": determinism_violation,
                            },
                            self.workspace,
                        )
                    result = {
                        "ok": False,
                        "error": determinism_violation,
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

                if protocol_enabled:
                    if not protocol_replay_mode:
                        invocation_manifest = build_tool_invocation_manifest(
                            run_id=session_id,
                            tool_name=tool_name,
                            ring=str((binding or {}).get("ring") or "core"),
                            schema_version=str((binding or {}).get("schema_version") or "1.0.0"),
                            determinism_class=str((binding or {}).get("determinism_class") or "workspace"),
                            capability_profile=str((binding or {}).get("capability_profile") or "workspace"),
                            tool_contract_version=str((binding or {}).get("tool_contract_version") or "1.0.0"),
                        )
                        tool_call_hash = compute_tool_call_hash(
                            tool_name=tool_name,
                            tool_args=dict(tool_call.args or {}),
                            tool_contract_version=str(invocation_manifest.get("tool_contract_version") or ""),
                            capability_profile=str(invocation_manifest.get("capability_profile") or ""),
                        )
                        await asyncio.to_thread(
                            self.persist_operation_result,
                            session_id=session_id,
                            issue_id=turn.issue_id,
                            role_name=turn.role,
                            turn_index=turn_index,
                            operation_id=operation_id,
                            tool_name=tool_name,
                            tool_args=dict(tool_call.args or {}),
                            result=result,
                        )
                        await asyncio.to_thread(
                            self.append_protocol_receipt,
                            session_id=session_id,
                            issue_id=turn.issue_id,
                            role_name=turn.role,
                            turn_index=turn_index,
                            receipt={
                                "run_id": session_id,
                                "step_id": step_id,
                                "receipt_seq": receipt_seq,
                                "operation_id": operation_id,
                                "proposal_hash": proposal_hash,
                                "validator_version": validator_version,
                                "protocol_hash": protocol_hash,
                                "tool_schema_hash": tool_schema_hash,
                                "tool_index": index,
                                "tool": tool_name,
                                "tool_args": dict(tool_call.args or {}),
                                "execution_result": result,
                                "tool_invocation_manifest": invocation_manifest,
                                "tool_call_hash": tool_call_hash,
                                "artifact_digests": [],
                                "retry_count": int(context.get("retry_count") or 0),
                                "validator_duration_ms": int(context.get("validator_duration_ms") or 0),
                                "execution_capsule": execution_capsule,
                                "replayed": bool(replayed),
                                **(
                                    {"compat_translation": dict(result.get("compat_translation") or {})}
                                    if isinstance(result, dict) and isinstance(result.get("compat_translation"), dict)
                                    else {}
                                ),
                            },
                        )
                elif not protocol_replay_mode:
                    await asyncio.to_thread(
                        self.persist_tool_result,
                        session_id=session_id,
                        issue_id=turn.issue_id,
                        role_name=turn.role,
                        turn_index=turn_index,
                        tool_name=tool_name,
                        tool_args=tool_call.args,
                        result=result,
                    )

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
                    violations.append(f"Tool {tool_name} failed: {result.get('error')}")
            except (ValueError, TypeError, KeyError, RuntimeError, OSError, AttributeError) as exc:
                tool_call.error = str(exc)
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
            raise self.tool_validation_error_factory(violations)

    def collect_protocol_preflight_violations(
        self,
        *,
        turn: ExecutionTurn,
        context: dict[str, Any],
        roles: list[str],
        approval_required_tools: set[str],
    ) -> list[str]:
        return collect_protocol_preflight_violations(
            turn=turn,
            context=context,
            roles=roles,
            approval_required_tools=approval_required_tools,
            tool_gate=self.tool_gate,
            workspace=self.workspace,
            resolve_skill_tool_binding=self.resolve_skill_tool_binding,
            missing_required_permissions=self.missing_required_permissions,
            runtime_limit_violations=self.runtime_limit_violations,
        )

    @staticmethod
    def resolve_skill_tool_binding(context: dict[str, Any], tool_name: str) -> dict[str, Any] | None:
        return resolve_skill_tool_binding(context, tool_name)

    def missing_required_permissions(self, binding: dict[str, Any], context: dict[str, Any]) -> list[str]:
        return missing_required_permissions(binding, context)

    @staticmethod
    def permission_values(values: Any) -> set[str]:
        return permission_values(values)

    def runtime_limit_violations(self, binding: dict[str, Any], context: dict[str, Any]) -> list[str]:
        return runtime_limit_violations(binding, context)

    @staticmethod
    def as_positive_float(value: Any) -> float | None:
        return as_positive_float(value)
