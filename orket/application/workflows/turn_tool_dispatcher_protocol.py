from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from functools import partial
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.tool_gate_service import ToolGate
from orket.core.contracts.card_completion_commit import is_card_completion_call
from orket.core.contracts.protocol_error_codes import (
    E_COMPAT_PARITY_VIOLATION_PREFIX,
    E_MAX_TOOL_CALLS_PREFIX,
    E_SCHEMA_TOOL_CALL_PREFIX,
    E_WORKSPACE_CONSTRAINT_PREFIX,
    format_protocol_error,
)
from orket.core.domain.execution import ExecutionTurn

from ..services.governed_turn_tool_approval_continuation_service import (
    supports_governed_turn_tool_approval_continuation,
)
from .turn_artifact_destination import TurnArtifactDestination
from .turn_artifact_writer import validate_operation_record
from .turn_contract_input_capture import capture_mapping, capture_protocol_context, capture_workspace
from .turn_read_context import (
    observe_legacy_required_read_paths,
    observe_workspace_constraint_violation,
)
from .turn_tool_dispatcher_compatibility import resolve_compatibility_translation
from .turn_tool_dispatcher_support import (
    required_sequence_violation,
    required_tools_violation,
    resolved_declared_namespace_scopes,
    resolved_tool_namespace_scope,
    tool_policy_violation,
)


async def collect_protocol_preflight_violations(
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
    captured_tool_calls: list[tuple[str, dict[str, Any]]] = []
    for index, tool_call in enumerate(turn.tool_calls):
        tool_name = str(tool_call.tool or "").strip()
        if not tool_name:
            return [format_protocol_error(E_SCHEMA_TOOL_CALL_PREFIX, f"{index}:tool")]
        if not isinstance(tool_call.args, dict):
            return [format_protocol_error(E_SCHEMA_TOOL_CALL_PREFIX, f"{index}:args")]
        observed_tool_names.append(tool_name)
        captured_tool_calls.append((tool_name, capture_mapping(tool_call.args)))

    captured_context = capture_protocol_context(context)
    captured_roles = list(roles)
    captured_approval_required_tools = frozenset(approval_required_tools)
    captured_workspace = capture_workspace(workspace)
    captured_issue_id = str(turn.issue_id)
    required_read_observation = await observe_legacy_required_read_paths(
        context=captured_context,
        workspace=captured_workspace,
    )

    required_tools_error = required_tools_violation(
        observed_tool_names=observed_tool_names,
        context=captured_context,
        required_read_path_count=len(required_read_observation.existing),
    )
    if required_tools_error:
        return [required_tools_error]

    sequence_error = required_sequence_violation(observed_tool_names=observed_tool_names, context=captured_context)
    if sequence_error:
        return [sequence_error]

    for tool_name, tool_args in captured_tool_calls:
        binding = resolve_skill_tool_binding(captured_context, tool_name)

        policy_violation = tool_policy_violation(
            tool_name=tool_name,
            binding=binding,
            context=captured_context,
            issue_id=captured_issue_id,
        )
        if policy_violation:
            return [policy_violation]
        _compatibility_translation, compatibility_violation = resolve_compatibility_translation(
            tool_name=tool_name,
            tool_args=tool_args,
            binding=binding,
            context=captured_context,
        )
        if compatibility_violation:
            return [compatibility_violation]

        workspace_violation = await observe_workspace_constraint_violation(
            tool_name=tool_name,
            args=tool_args,
            workspace=captured_workspace,
        )
        if workspace_violation:
            return [format_protocol_error(E_WORKSPACE_CONSTRAINT_PREFIX, workspace_violation)]

        gate_violation = await tool_gate.validate(
            tool_name=tool_name,
            args=tool_args,
            context=captured_context,
            roles=captured_roles,
        )
        if gate_violation:
            return [f"Governance Violation: {gate_violation}"]

        if bool(captured_context.get("skill_contract_enforced")):
            if binding is None:
                return [f"Skill contract violation: undeclared entrypoint/tool '{tool_name}'."]
            missing_permissions = missing_required_permissions(binding, captured_context)
            if missing_permissions:
                return [
                    "Skill contract violation: missing required permissions for "
                    f"'{tool_name}' ({', '.join(missing_permissions)})."
                ]
            limit_violations = runtime_limit_violations(binding, captured_context)
            if limit_violations:
                return [
                    "Skill contract violation: runtime limits exceeded for "
                    f"'{tool_name}' ({', '.join(limit_violations)})."
                ]

        if tool_name in captured_approval_required_tools:
            if supports_governed_turn_tool_approval_continuation(
                tool_name=tool_name,
                context=captured_context,
                issue_id=captured_issue_id,
            ):
                continue
            return [f"Approval required for tool '{tool_name}' before execution."]
    return []


async def load_or_execute_tool(
    *,
    protocol_enabled: bool,
    control_plane_enabled: bool,
    destination: TurnArtifactDestination,
    turn: ExecutionTurn,
    tool_name: str,
    tool_args: dict[str, Any],
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
    prepare_dispatch: Callable[..., Awaitable[None]],
) -> tuple[dict[str, Any], bool, bool]:
    tool_args, binding = deepcopy((tool_args, binding))
    if bool(context.get("protocol_replay_mode")):
        operation_record = await run_owned_thread(partial(
            load_operation_result, destination=destination, operation_id=operation_id,
        ), label="turn-operation-cache-read")
        if operation_record is None:
            raise ValueError("E_REPLAY_OPERATION_MISSING")
        return validate_operation_record(operation_record, operation_id=operation_id,
            tool_name=tool_name, tool_args=tool_args), True, True
    completion_call = is_card_completion_call(tool_name, tool_args)
    if (protocol_enabled or control_plane_enabled) and not completion_call:
        operation_record = await run_owned_thread(partial(
            load_operation_result, destination=destination, operation_id=operation_id,
        ), label="turn-operation-cache-read")
        if operation_record is not None:
            replay_result = validate_operation_record(operation_record, operation_id=operation_id,
                tool_name=tool_name, tool_args=tool_args)
            await prepare_dispatch(
                tool_name=tool_name, tool_args=tool_args, binding=binding, operation_id=operation_id,
                replay_operation=True,
            )
            return replay_result, True, True
    replay_result = None if completion_call else await run_owned_thread(partial(
        load_replay_tool_result, destination=destination,
        tool_name=tool_name,
        tool_args=tool_args,
        resume_mode=bool(context.get("resume_mode")),
    ), label="turn-tool-cache-read")
    if replay_result is not None:
        await prepare_dispatch(
            tool_name=tool_name, tool_args=tool_args, binding=binding, operation_id=operation_id,
            replay_operation=True,
        )
        return replay_result, True, False

    execution_context = dict(context)
    if isinstance(binding, dict):
        execution_context["skill_entrypoint_id"] = str(binding.get("entrypoint_id") or "")
        execution_context["skill_runtime"] = str(binding.get("runtime") or "")
        execution_context["skill_runtime_version"] = str(binding.get("runtime_version") or "")
        execution_context["tool_runtime_limits"] = dict(binding.get("runtime_limits") or {})
    execution_context["tool_declared_namespace_scopes"] = resolved_declared_namespace_scopes(
        binding=binding, context=context, issue_id=turn.issue_id)
    execution_context["tool_namespace_scope"] = resolved_tool_namespace_scope(
        binding=binding, context=context, issue_id=turn.issue_id)
    execution_context["run_namespace_scope"] = resolved_tool_namespace_scope(
        binding=None,
        context=context,
        issue_id=turn.issue_id,
    )
    execution_context["step_id"] = step_id
    execution_context["step_seed"] = step_seed
    execution_context["operation_id"] = operation_id
    execution_context["validator_version"] = validator_version
    execution_context["protocol_hash"] = protocol_hash
    execution_context["tool_schema_hash"] = tool_schema_hash
    await prepare_dispatch(tool_name=tool_name, tool_args=tool_args, binding=binding,
                           operation_id=operation_id, replay_operation=False)
    if isinstance(compatibility_translation, dict):
        result = await _execute_compatibility_translation(
            toolbox=toolbox,
            execution_context=execution_context,
            compatibility_translation=compatibility_translation,
        )
    else:
        result = await toolbox.execute(tool_name, tool_args, execution_context)
    return result if isinstance(result, dict) else {"ok": False, "error": "non_dict_result"}, False, False


async def _execute_compatibility_translation(
    *,
    toolbox: Any,
    execution_context: dict[str, Any],
    compatibility_translation: dict[str, Any],
) -> dict[str, Any]:
    started = asyncio.get_running_loop().time()
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
        mapped_started = asyncio.get_running_loop().time()
        mapped_result_raw = await toolbox.execute(mapped_tool, mapped_args, call_context)
        mapped_latency_ms = int((asyncio.get_running_loop().time() - mapped_started) * 1000)
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
                "latency_ms": mapped_latency_ms,
            }
        )
        if not bool(mapped_result.get("ok", False)):
            return {
                "ok": False,
                "error": format_protocol_error(E_COMPAT_PARITY_VIOLATION_PREFIX, f"mapped_tool_failed:{mapped_tool}"),
                "compat_translation": artifact,
                "mapped_results": mapped_results,
            }

    total_latency_ms = int((asyncio.get_running_loop().time() - started) * 1000)
    artifact["latency_ms"] = total_latency_ms
    return {
        "ok": True,
        "compat_translation": artifact,
        "mapped_results": mapped_results,
    }
