"""Turn executor coordinator with delegated workflow components."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneService
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_contract_validator import ContractValidator
from orket.application.workflows.turn_corrective_prompt import CorrectivePromptBuilder
from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.application.workflows.turn_path_resolver import PathResolver
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.domain.execution import ExecutionTurn
from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.core.policies.tool_gate import ToolGate
from orket.exceptions import ModelConnectionError, ModelProviderError, ModelTimeoutError
from orket.schema import CardStatus, IssueConfig, RoleConfig

from . import turn_executor_ops


@dataclass
class TurnResult:
    """Result of executing a single turn."""

    success: bool
    turn: ExecutionTurn | None = None
    error: str | None = None
    should_retry: bool = False
    violations: list[str] = field(default_factory=list)

    @classmethod
    def succeeded(cls, turn: ExecutionTurn) -> TurnResult:
        return cls(success=True, turn=turn)

    @classmethod
    def failed(cls, error: str, should_retry: bool = False) -> TurnResult:
        return cls(success=False, error=error, should_retry=should_retry)

    @classmethod
    def governance_violation(cls, violations: list[str]) -> TurnResult:
        return cls(
            success=False,
            error=f"Governance violations: {violations}",
            should_retry=True,
            violations=violations,
        )


class TurnExecutor:
    """Coordinator for single-turn execution workflow."""

    def __init__(
        self,
        state_machine: StateMachine,
        tool_gate: ToolGate,
        workspace: Path,
        middleware: TurnLifecycleInterceptors | None = None,
        control_plane_service: TurnToolControlPlaneService | None = None,
    ) -> None:
        self.state = state_machine
        self.tool_gate = tool_gate
        self.workspace = workspace
        self.middleware = middleware or TurnLifecycleInterceptors([])
        self.middleware.bind_workspace(self.workspace)

        self.artifact_writer = TurnArtifactWriter(workspace)
        self.response_parser = ResponseParser(workspace, self.artifact_writer.write_turn_artifact)
        self.message_builder = MessageBuilder(workspace)
        self.corrective_prompt_builder = CorrectivePromptBuilder(workspace)
        self.contract_validator = ContractValidator(workspace, self.response_parser)
        self.tool_dispatcher = ToolDispatcher(
            tool_gate=self.tool_gate,
            middleware=self.middleware,
            workspace=self.workspace,
            append_memory_event=self.artifact_writer.append_memory_event,
            hash_payload=self.artifact_writer.hash_payload,
            load_replay_tool_result=self.artifact_writer.load_replay_tool_result,
            persist_tool_result=self.artifact_writer.persist_tool_result,
            load_operation_result=self.artifact_writer.load_operation_result,
            persist_operation_result=self.artifact_writer.persist_operation_result,
            append_protocol_receipt=self.artifact_writer.append_protocol_receipt,
            tool_approval_pending_error_factory=lambda message: ToolApprovalPendingError(message),
            tool_validation_error_factory=lambda violations: ToolValidationError(violations),
            control_plane_service=control_plane_service,
        )

    async def execute_turn(
        self,
        issue: IssueConfig,
        role: RoleConfig,
        model_client: Any,
        toolbox: Any,
        context: dict[str, Any],
        system_prompt: str | None = None,
    ) -> TurnResult:
        return await turn_executor_ops.execute_turn(self, issue, role, model_client, toolbox, context, system_prompt)

    async def _prepare_messages(
        self,
        issue: IssueConfig,
        role: RoleConfig,
        context: dict[str, Any],
        system_prompt: str | None = None,
        ) -> list[dict[str, str]]:
        return await self.message_builder.prepare_messages(
            issue=issue,
            role=role,
            context=context,
            system_prompt=system_prompt,
        )

    def _validate_preconditions(self, issue: IssueConfig, role: RoleConfig, context: dict[str, Any]) -> None:
        if "session_id" not in context:
            raise ValueError("session_id required in context")
        if "current_status" not in context:
            raise ValueError("current_status required in context")

        allowed_types = role.capabilities.get("issue_types")
        if allowed_types is None:
            allowed_types = ["issue", "story", "bug", "task"]

        current_type = issue.type.value if hasattr(issue.type, "value") else str(issue.type)
        if current_type not in allowed_types:
            raise ValueError(f"Role {role.name} cannot handle {current_type} issues (Allowed: {allowed_types})")

        issue_status = CardStatus(issue.status)
        try:
            context_status = CardStatus(str(context.get("current_status")).strip().lower())
        except ValueError as exc:
            raise ValueError(f"Invalid current_status in context: {context.get('current_status')}") from exc

        if context_status not in [
            CardStatus.IN_PROGRESS,
            CardStatus.CODE_REVIEW,
            CardStatus.AWAITING_GUARD_REVIEW,
        ]:
            raise StateMachineError(f"Issue {issue.id} cannot execute turn from context status {context_status.value}")

        if issue_status != context_status:
            raise StateMachineError(
                "Issue "
                f"{issue.id} status/context mismatch: issue.status={issue_status.value}, "
                f"context.current_status={context_status.value}"
            )


class ToolValidationError(Exception):
    """Tool call validation failed."""

    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__(f"Tool validation failed: {violations}")


class ToolApprovalPendingError(Exception):
    """Tool execution is paused on an admitted approval-required slice."""

    def __init__(self, message: str):
        self.message = str(message or "").strip() or "Approval required before execution."
        super().__init__(self.message)


__all__ = [
    "ContractValidator",
    "CorrectivePromptBuilder",
    "MessageBuilder",
    "ModelConnectionError",
    "ModelProviderError",
    "ModelTimeoutError",
    "PathResolver",
    "ResponseParser",
    "ToolApprovalPendingError",
    "ToolDispatcher",
    "ToolValidationError",
    "TurnArtifactWriter",
    "TurnExecutor",
    "TurnResult",
]
