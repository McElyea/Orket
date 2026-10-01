from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.services.card_completion_turn_service import verify_turn_completion_claims
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneService
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.core.domain.execution import ExecutionTurn, ToolCallErrorClass
from orket.schema import IssueConfig

from .turn_artifact_destination import TurnArtifactDestination
from .turn_contract_input_capture import execute_with_protocol_capture
from .turn_control_plane_binding import TurnControlPlaneBinding
from .turn_memory_trace_artifacts import MemoryTraceInputs
from .turn_tool_dispatch_checks import approve_tool, before_tool, prepare_dispatch_run, validate_tool
from .turn_tool_dispatch_context import capture_dispatch_run, capture_dispatch_step
from .turn_tool_dispatch_results import (
    invoke_tool,
    observe_tool_result,
    publish_tool_result,
    record_tool_failure,
    record_tool_outcome,
)
from .turn_tool_dispatcher_compatibility import resolve_compatibility_translation
from .turn_tool_dispatcher_control_plane import finalize_execution_if_needed
from .turn_tool_dispatcher_support import (
    as_positive_float,
    missing_required_permissions,
    permission_values,
    resolve_skill_tool_binding,
    runtime_limit_violations,
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
        self.tool_approval_pending_error_factory = tool_approval_pending_error_factory or (
            lambda message: RuntimeError(str(message or ""))
        )
        self.tool_validation_error_factory = tool_validation_error_factory or (
            lambda violations: RuntimeError(str(list(violations or [])))
        )
        self.control_plane_service = control_plane_service

    async def execute_tools(
        self,
        *,
        turn: ExecutionTurn,
        toolbox: Any,
        context: dict[str, Any],
        destination: TurnArtifactDestination,
        memory_inputs: MemoryTraceInputs,
        control_plane: TurnControlPlaneBinding,
        memory_events: list[dict[str, Any]] | None,
        issue: IssueConfig | None = None,
        on_turn_captured: Callable[[ExecutionTurn], None] | None = None,
    ) -> ExecutionTurn:
        if control_plane.dispatcher is not self:
            raise ValueError("E_TURN_DISPATCH_OWNER_MISMATCH")
        return await execute_with_protocol_capture(
            execute=partial(
                self._execute_tools_captured,
                destination=destination,
                memory_inputs=memory_inputs,
                memory_events=memory_events,
                control_plane=control_plane,
            ),
            turn=turn,
            toolbox=toolbox,
            context=context,
            destination=destination,
            control_plane=control_plane,
            issue=issue,
            on_turn_captured=on_turn_captured,
        )

    async def _execute_tools_captured(
        self,
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
    ) -> None:
        run = capture_dispatch_run(
            self,
            turn=turn,
            toolbox=toolbox,
            context=context,
            workspace=workspace,
            destination=destination,
            memory_inputs=memory_inputs,
            control_plane=control_plane,
            memory_events=memory_events,
            issue=issue,
        )
        await prepare_dispatch_run(run)
        for index, tool_call in enumerate(turn.tool_calls):
            step = capture_dispatch_step(run, index, tool_call)
            try:
                if not before_tool(run, step):
                    continue
                if not await validate_tool(run, step):
                    continue
                if not await approve_tool(run, step):
                    continue
                compatibility_translation, compatibility_violation = resolve_compatibility_translation(
                    tool_name=step.tool_name,
                    tool_args=dict(step.tool_call.args or {}),
                    binding=step.binding,
                    context=run.context,
                )
                if compatibility_violation:
                    step.tool_call.error = compatibility_violation
                    step.tool_call.error_class = ToolCallErrorClass.GATE_BLOCKED
                    run.violations.append(compatibility_violation)
                    continue
                result, replayed, operation_record_present = await invoke_tool(run, step, compatibility_translation)
                result = observe_tool_result(run, step, result, replayed)
                await publish_tool_result(run, step, result, replayed, operation_record_present)
                record_tool_outcome(run, step, result, replayed)
            except (ValueError, TypeError, KeyError, RuntimeError, OSError, AttributeError) as exc:
                record_tool_failure(run, step, exc)
        if not run.violations:
            try:
                await verify_turn_completion_claims(toolbox=run.toolbox, turn=run.turn, context=run.context)
            except (CardCompletionRejected, AttributeError) as exc:
                run.violations.append(f"Card completion claim rejected: {exc}")
        await finalize_execution_if_needed(
            control_plane_enabled=run.control_plane_enabled,
            control_plane_service=run.control_plane_service,
            control_plane_run_id=run.control_plane_run_id,
            control_plane_attempt_id=run.control_plane_attempt_id,
            authoritative_result_ref=run.last_result_ref
            or f"turn-tool-{('violations' if run.violations else 'complete')}:{run.control_plane_run_id}",
            violation_reasons=run.violations,
            executed_step_count=run.executed_step_count,
        )
        if run.violations:
            raise run.owner.tool_validation_error_factory(run.violations)
