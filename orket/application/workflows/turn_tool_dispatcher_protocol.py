from __future__ import annotations

import asyncio
from typing import Any, Callable

from orket.core.policies.tool_gate import ToolGate
from orket.domain.execution import ExecutionTurn
from orket.runtime.protocol_error_codes import (
    E_COMPAT_PARITY_VIOLATION_PREFIX,
    E_MAX_TOOL_CALLS_PREFIX,
    E_SCHEMA_TOOL_CALL_PREFIX,
    E_WORKSPACE_CONSTRAINT_PREFIX,
    format_protocol_error,
)

from .turn_tool_dispatcher_compatibility import resolve_compatibility_translation
from .turn_path_resolver import PathResolver
from .turn_tool_dispatcher_support import (
    required_sequence_violation,
    required_tools_violation,
    tool_policy_violation,
)


def collect_protocol_preflight_violations(
    *,
    turn: ExecutionTurn,
    context: dict[str, Any],
    roles: list[str],
    approval_required_tools: set[str],
    tool_gate: ToolGate,
    workspace: Any,
    resolve_skill_tool_binding: Callable[[dict[str, Any], str], dict[str, Any] | None],
    missing_required_permissions: Callable[[dict[str, Any], dict[str, Any]], list[str]],
    runtime_limit_violations: Callable[[dict[str, Any], dict[str, Any]], list[str]],
) -> list[str]:
    try:
        max_tool_calls = max(1, int(context.get("max_tool_calls", 8)))
    except (TypeError, ValueError):
        max_tool_calls = 8
    if len(turn.tool_calls) > max_tool_calls:
        return [format_protocol_error(E_MAX_TOOL_CALLS_PREFIX, f"{len(turn.tool_calls)}>{max_tool_calls}")]

    observed_tool_names: list[str] = []
    for index, tool_call in enumerate(turn.tool_calls):
        tool_name = str(tool_call.tool or "").strip()
        if not tool_name:
            return [format_protocol_error(E_SCHEMA_TOOL_CALL_PREFIX, f"{index}:tool")]
        if not isinstance(tool_call.args, dict):
            return [format_protocol_error(E_SCHEMA_TOOL_CALL_PREFIX, f"{index}:args")]
        observed_tool_names.append(tool_name)

    required_tools_error = required_tools_violation(observed_tool_names=observed_tool_names, context=context)
    if required_tools_error:
        return [required_tools_error]

    sequence_error = required_sequence_violation(observed_tool_names=observed_tool_names, context=context)
    if sequence_error:
        return [sequence_error]

    for index, tool_call in enumerate(turn.tool_calls):
        tool_name = str(tool_call.tool or "").strip()
        binding = resolve_skill_tool_binding(context, tool_name)

        policy_violation = tool_policy_violation(
            tool_name=tool_name,
            binding=binding,
            context=context,
        )
        if policy_violation:
            return [policy_violation]
        _compatibility_translation, compatibility_violation = resolve_compatibility_translation(
            tool_name=tool_name,
            tool_args=dict(tool_call.args or {}),
            binding=binding,
            context=context,
        )
        if compatibility_violation:
            return [compatibility_violation]

        workspace_violation = PathResolver.workspace_constraint_violation(
            tool_name=tool_name,
            args=dict(tool_call.args or {}),
            workspace=workspace,
        )
        if workspace_violation:
            return [format_protocol_error(E_WORKSPACE_CONSTRAINT_PREFIX, workspace_violation)]

        gate_violation = tool_gate.validate(
            tool_name=tool_name,
            args=tool_call.args,
            context=context,
            roles=roles,
        )
        if gate_violation:
            return [f"Governance Violation: {gate_violation}"]

        if bool(context.get("skill_contract_enforced")):
            if binding is None:
                return [f"Skill contract violation: undeclared entrypoint/tool '{tool_name}'."]
            missing_permissions = missing_required_permissions(binding, context)
            if missing_permissions:
                return [
                    "Skill contract violation: missing required permissions for "
                    f"'{tool_name}' ({', '.join(missing_permissions)})."
                ]
            limit_violations = runtime_limit_violations(binding, context)
            if limit_violations:
                return [
                    "Skill contract violation: runtime limits exceeded for "
                    f"'{tool_name}' ({', '.join(limit_violations)})."
                ]

        if tool_name in approval_required_tools:
            return [f"Approval required for tool '{tool_name}' before execution."]

        if not isinstance(tool_call.args, dict):
            return [format_protocol_error(E_SCHEMA_TOOL_CALL_PREFIX, f"{index}:args")]
    return []


async def load_or_execute_tool(
    *,
    protocol_enabled: bool,
    session_id: str,
    turn: ExecutionTurn,
    tool_name: str,
    tool_args: dict[str, Any],
    turn_index: int,
    operation_id: str,
    binding: dict[str, Any] | None,
    toolbox: Any,
    context: dict[str, Any],
    step_id: str,
    step_seed: str,
    validator_version: str,
    protocol_hash: str,
    tool_schema_hash: str,
    compatibility_translation: dict[str, Any] | None = None,
    load_operation_result: Callable[..., dict[str, Any] | None],
    load_replay_tool_result: Callable[..., dict[str, Any] | None],
) -> tuple[dict[str, Any], bool]:
    if bool(context.get("protocol_replay_mode")):
        operation_record = await asyncio.to_thread(
            load_operation_result,
            session_id=session_id,
            issue_id=turn.issue_id,
            role_name=turn.role,
            turn_index=turn_index,
            operation_id=operation_id,
        )
        if isinstance(operation_record, dict):
            replay_result = operation_record.get("result")
            if isinstance(replay_result, dict):
                return replay_result, True
        raise ValueError("E_REPLAY_OPERATION_MISSING")

    if protocol_enabled:
        operation_record = await asyncio.to_thread(
            load_operation_result,
            session_id=session_id,
            issue_id=turn.issue_id,
            role_name=turn.role,
            turn_index=turn_index,
            operation_id=operation_id,
        )
        if isinstance(operation_record, dict):
            replay_result = operation_record.get("result")
            if isinstance(replay_result, dict):
                return replay_result, True

    replay_result = await asyncio.to_thread(
        load_replay_tool_result,
        session_id=session_id,
        issue_id=turn.issue_id,
        role_name=turn.role,
        turn_index=turn_index,
        tool_name=tool_name,
        tool_args=tool_args,
        resume_mode=bool(context.get("resume_mode")),
    )
    if replay_result is not None:
        return replay_result, True

    execution_context = dict(context)
    if isinstance(binding, dict):
        execution_context["skill_entrypoint_id"] = str(binding.get("entrypoint_id") or "")
        execution_context["skill_runtime"] = str(binding.get("runtime") or "")
        execution_context["skill_runtime_version"] = str(binding.get("runtime_version") or "")
        execution_context["tool_runtime_limits"] = dict(binding.get("runtime_limits") or {})
    execution_context["step_id"] = step_id
    execution_context["step_seed"] = step_seed
    execution_context["operation_id"] = operation_id
    execution_context["validator_version"] = validator_version
    execution_context["protocol_hash"] = protocol_hash
    execution_context["tool_schema_hash"] = tool_schema_hash
    if isinstance(compatibility_translation, dict):
        result = await _execute_compatibility_translation(
            toolbox=toolbox,
            execution_context=execution_context,
            compatibility_translation=compatibility_translation,
        )
    else:
        result = await toolbox.execute(tool_name, tool_args, execution_context)
    return result if isinstance(result, dict) else {"ok": False, "error": "non_dict_result"}, False


async def _execute_compatibility_translation(
    *,
    toolbox: Any,
    execution_context: dict[str, Any],
    compatibility_translation: dict[str, Any],
) -> dict[str, Any]:
    translated_calls = compatibility_translation.get("translated_calls")
    translated_calls = translated_calls if isinstance(translated_calls, list) else []
    artifact = compatibility_translation.get("artifact")
    artifact = dict(artifact) if isinstance(artifact, dict) else {}
    if not translated_calls:
        return {
            "ok": False,
            "error": format_protocol_error(E_COMPAT_PARITY_VIOLATION_PREFIX, "translation_empty"),
            "compat_translation": artifact,
            "mapped_results": [],
        }

    mapped_results: list[dict[str, Any]] = []
    for translated in translated_calls:
        if not isinstance(translated, dict):
            return {
                "ok": False,
                "error": format_protocol_error(E_COMPAT_PARITY_VIOLATION_PREFIX, "translation_schema"),
                "compat_translation": artifact,
                "mapped_results": mapped_results,
            }
        mapped_tool = str(translated.get("tool_name") or "").strip()
        mapped_args = translated.get("tool_args")
        mapped_args = dict(mapped_args) if isinstance(mapped_args, dict) else {}
        if not mapped_tool:
            return {
                "ok": False,
                "error": format_protocol_error(E_COMPAT_PARITY_VIOLATION_PREFIX, "mapped_tool_name"),
                "compat_translation": artifact,
                "mapped_results": mapped_results,
            }
        call_context = dict(execution_context)
        call_context["compatibility_parent_tool"] = str(artifact.get("compat_tool_name") or "")
        call_context["compatibility_mapping_version"] = artifact.get("mapping_version")
        mapped_result_raw = await toolbox.execute(mapped_tool, mapped_args, call_context)
        mapped_result = (
            dict(mapped_result_raw)
            if isinstance(mapped_result_raw, dict)
            else {"ok": False, "error": "non_dict_result"}
        )
        mapped_results.append(
            {
                "tool_name": mapped_tool,
                "tool_args": mapped_args,
                "result": dict(mapped_result),
            }
        )
        if not bool(mapped_result.get("ok", False)):
            return {
                "ok": False,
                "error": format_protocol_error(E_COMPAT_PARITY_VIOLATION_PREFIX, f"mapped_tool_failed:{mapped_tool}"),
                "compat_translation": artifact,
                "mapped_results": mapped_results,
            }

    return {
        "ok": True,
        "compat_translation": artifact,
        "mapped_results": mapped_results,
    }
