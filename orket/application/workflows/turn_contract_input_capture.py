from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.schema import RoleConfig

from .turn_read_context import RequiredReadObservation, observe_legacy_required_read_paths

_VALIDATION_CONTEXT_KEYS = frozenset(
    {
        "architecture_allowed_patterns",
        "architecture_decision_path",
        "architecture_decision_required",
        "architecture_forced_pattern",
        "architecture_mode",
        "artifact_contract",
        "dependency_context",
        "frontend_framework_allowed",
        "frontend_framework_forced",
        "local_prompt_allows_thinking_blocks",
        "local_prompt_intro_denylist",
        "local_prompt_task_class",
        "local_prompt_thinking_block_format",
        "protocol_governed_enabled",
        "required_action_tools",
        "required_comment_contains",
        "required_comment_min_length",
        "required_read_paths",
        "required_statuses",
        "required_write_paths",
        "stage_gate_mode",
        "verification_scope",
    }
)

_PROTOCOL_CONTEXT_KEYS = frozenset(
    {
        "allowed_capability_profiles",
        "allowed_namespace_scopes",
        "allowed_tool_rings",
        "approval_required_tools",
        "capabilities_allowed",
        "card_id",
        "card_type",
        "clock_artifact_hash",
        "clock_artifact_ref",
        "clock_mode",
        "compatibility_mappings",
        "current_role",
        "current_status",
        "env_allowlist",
        "env_allowlist_hash",
        "executor_image_digest",
        "granted_permissions",
        "idesign_enabled",
        "invoked_from_tool",
        "issue_id",
        "locale",
        "max_tool_calls",
        "max_tool_execution_time",
        "max_tool_memory",
        "network_allowlist_hash",
        "network_allowlist_values",
        "network_mode",
        "normalization_version",
        "os_arch",
        "protocol_hash",
        "protocol_replay_mode",
        "required_action_tools",
        "required_read_paths",
        "required_sequence",
        "required_tool_sequence",
        "resume_mode",
        "retry_count",
        "role",
        "roles",
        "run_seed",
        "run_determinism_class",
        "run_determinism_policy",
        "run_namespace_scope",
        "session_id",
        "skill_contract_enforced",
        "skill_tool_bindings",
        "stage_gate_mode",
        "timezone",
        "tool_profile_version",
        "tool_schema_hash",
        "toolchain_version_set",
        "turn_index",
        "validator_version",
    }
)


@dataclass(frozen=True)
class ValidationAttemptInputs:
    turn: ExecutionTurn
    role: RoleConfig
    context: dict[str, Any]
    workspace: Path
    required_read_observation: RequiredReadObservation | None


_EMPTY_REQUIRED_READ_OBSERVATION = RequiredReadObservation(existing=(), missing=())


@dataclass(frozen=True)
class ProtocolDispatchInputs:
    turn: ExecutionTurn
    context: dict[str, Any]
    workspace: Path
    original_tool_calls: tuple[ToolCall, ...]


async def observe_validation_attempt(
    *, turn: ExecutionTurn, role: RoleConfig, context: Mapping[str, Any], workspace: Path,
) -> ValidationAttemptInputs:
    captured_turn = capture_validation_turn(turn)
    captured_role = capture_validation_role(role)
    captured_context = capture_validation_context(context)
    captured_workspace = capture_workspace(workspace)
    observation = None
    if not captured_turn.partial_parse_failure:
        observation = await observe_legacy_required_read_paths(
            context=captured_context,
            workspace=captured_workspace,
        )
    return ValidationAttemptInputs(captured_turn, captured_role, captured_context, captured_workspace, observation)


async def collect_validation_attempt(
    *, validator: Any, turn: ExecutionTurn, role: RoleConfig,
    context: Mapping[str, Any], workspace: Path,
) -> tuple[ValidationAttemptInputs, list[dict[str, Any]]]:
    attempt = await observe_validation_attempt(
        turn=turn, role=role, context=context, workspace=workspace,
    )
    violations = validator.collect_contract_violations(
        attempt.turn,
        attempt.role,
        attempt.context,
        attempt.required_read_observation or _EMPTY_REQUIRED_READ_OBSERVATION,
    )
    return attempt, violations


async def required_read_observation_for_correction(
    *, attempt: ValidationAttemptInputs,
) -> RequiredReadObservation:
    if attempt.required_read_observation is not None:
        return attempt.required_read_observation
    return await observe_legacy_required_read_paths(context=attempt.context, workspace=attempt.workspace)


def contract_reasons(contract_violations: list[dict[str, Any]]) -> list[str]:
    return [
        str(item.get("reason", "")).strip()
        for item in contract_violations
        if str(item.get("reason", "")).strip()
    ]


def capture_validation_context(context: Mapping[str, Any]) -> dict[str, Any]:
    return _capture_context(context, _VALIDATION_CONTEXT_KEYS)


def capture_protocol_context(context: Mapping[str, Any]) -> dict[str, Any]:
    return _capture_context(context, _PROTOCOL_CONTEXT_KEYS)


def capture_dispatch_context(context: Mapping[str, Any]) -> dict[str, Any]:
    # Unknown extension values are borrowed owners or sinks and retain identity.
    return _capture_context(context, _PROTOCOL_CONTEXT_KEYS)


def capture_workspace(workspace: Path) -> Path:
    captured_workspace, = capture_file_roots([workspace])
    return captured_workspace


def capture_protocol_dispatch(
    *, turn: ExecutionTurn, context: Mapping[str, Any], workspace: Path,
) -> ProtocolDispatchInputs:
    return ProtocolDispatchInputs(
        turn=capture_validation_turn(turn),
        context=capture_dispatch_context(context),
        workspace=capture_workspace(workspace),
        original_tool_calls=tuple(turn.tool_calls),
    )


def publish_protocol_tool_outcomes(inputs: ProtocolDispatchInputs) -> None:
    for original, captured in zip(inputs.original_tool_calls, inputs.turn.tool_calls, strict=True):
        original.result = captured.result
        original.error = captured.error
        original.error_class = captured.error_class


async def execute_with_protocol_capture(
    *, execute: Callable[..., Awaitable[None]], turn: ExecutionTurn, toolbox: Any,
    context: dict[str, Any], workspace: Path, issue: Any,
    on_turn_captured: Callable[[ExecutionTurn], None] | None = None,
) -> ExecutionTurn:
    if not bool(context.get("protocol_governed_enabled", False)):
        if on_turn_captured is not None:
            on_turn_captured(turn)
        await execute(turn=turn, toolbox=toolbox, context=context, workspace=workspace, issue=issue)
        return turn
    inputs = capture_protocol_dispatch(turn=turn, context=context, workspace=workspace)
    if on_turn_captured is not None:
        on_turn_captured(inputs.turn)
    try:
        await execute(
            turn=inputs.turn, toolbox=toolbox, context=inputs.context,
            workspace=inputs.workspace, issue=issue,
        )
    finally:
        publish_protocol_tool_outcomes(inputs)
    return inputs.turn


def capture_validation_turn(turn: ExecutionTurn) -> ExecutionTurn:
    return ExecutionTurn(
        timestamp=turn.timestamp,
        role=str(turn.role),
        issue_id=str(turn.issue_id),
        thought=turn.thought,
        content=str(turn.content or ""),
        tool_calls=[
            ToolCall(
                tool=str(call.tool or ""),
                args=_capture_value(call.args) if isinstance(call.args, dict) else call.args,
                result=call.result,
                error=call.error,
                error_class=call.error_class,
            )
            for call in turn.tool_calls
        ],
        tokens_used=turn.tokens_used,
        note=str(turn.note or ""),
        raw=_capture_value(turn.raw) if isinstance(turn.raw, dict) else {},
        partial_parse_failure=turn.partial_parse_failure,
        error=turn.error,
        error_class=turn.error_class,
    )


def capture_validation_role(role: RoleConfig) -> RoleConfig:
    return role.model_copy(update={"tools": list(role.tools or [])})


def capture_mapping(value: dict[str, Any]) -> dict[str, Any]:
    return _capture_value(value)


def _capture_context(context: Mapping[str, Any], detached_keys: frozenset[str]) -> dict[str, Any]:
    captured = dict(context)
    for key in detached_keys.intersection(captured):
        captured[key] = _capture_value(captured[key])
    return captured


def _capture_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _capture_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_capture_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_capture_value(item) for item in value)
    if isinstance(value, set):
        return {_capture_value(item) for item in value}
    return value
