"""Turn executor coordinator with delegated workflow components."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_contract_validator import ContractValidator
from orket.application.workflows.turn_corrective_prompt import CorrectivePromptBuilder
from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.application.workflows.turn_path_resolver import PathResolver
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.core.policies.tool_gate import ToolGate
from orket.domain.execution import ExecutionTurn
from orket.schema import CardStatus, IssueConfig, RoleConfig

from . import turn_executor_ops


@dataclass
class TurnResult:
    """Result of executing a single turn."""

    success: bool
    turn: Optional[ExecutionTurn] = None
    error: Optional[str] = None
    should_retry: bool = False
    violations: List[str] = None

    @classmethod
    def succeeded(cls, turn: ExecutionTurn) -> TurnResult:
        return cls(success=True, turn=turn)

    @classmethod
    def failed(cls, error: str, should_retry: bool = False) -> TurnResult:
        return cls(success=False, error=error, should_retry=should_retry)

    @classmethod
    def governance_violation(cls, violations: List[str]) -> TurnResult:
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
        middleware: Optional[TurnLifecycleInterceptors] = None,
    ):
        self.state = state_machine
        self.tool_gate = tool_gate
        self.workspace = workspace
        self.middleware = middleware or TurnLifecycleInterceptors([])

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
            tool_validation_error_factory=lambda violations: ToolValidationError(violations),
        )

    def __getattr__(self, name: str) -> Any:
        delegated = {
            "_prepare_messages": self.message_builder.prepare_messages,
            "_parse_response": self.response_parser.parse_response,
            "_non_json_residue": self.response_parser.non_json_residue,
            "_extract_guard_review_payload": self.response_parser.extract_guard_review_payload,
            "_execute_tools": self.tool_dispatcher.execute_tools,
            "_resolve_skill_tool_binding": self.tool_dispatcher.resolve_skill_tool_binding,
            "_missing_required_permissions": self.tool_dispatcher.missing_required_permissions,
            "_permission_values": self.tool_dispatcher.permission_values,
            "_runtime_limit_violations": self.tool_dispatcher.runtime_limit_violations,
            "_as_positive_float": self.tool_dispatcher.as_positive_float,
            "_collect_contract_violations": self.contract_validator.collect_contract_violations,
            "_progress_contract_diagnostics": self.contract_validator.progress_contract_diagnostics,
            "_meets_progress_contract": self.contract_validator.meets_progress_contract,
            "_meets_write_path_contract": self.contract_validator.meets_write_path_contract,
            "_meets_guard_rejection_payload_contract": self.contract_validator.meets_guard_rejection_payload_contract,
            "_meets_read_path_contract": self.contract_validator.meets_read_path_contract,
            "_meets_architecture_decision_contract": self.contract_validator.meets_architecture_decision_contract,
            "_parse_architecture_decision_payload": self.contract_validator.parse_architecture_decision_payload,
            "_hallucination_scope_diagnostics": self.contract_validator.hallucination_scope_diagnostics,
            "_security_scope_diagnostics": self.contract_validator.security_scope_diagnostics,
            "_consistency_scope_diagnostics": self.contract_validator.consistency_scope_diagnostics,
            "_build_corrective_instruction": self.corrective_prompt_builder.build_corrective_instruction,
            "_rule_specific_fix_hints": self.corrective_prompt_builder.rule_specific_fix_hints,
            "_hint_for_rule_id": self.corrective_prompt_builder.hint_for_rule_id,
            "_deterministic_failure_message": self.corrective_prompt_builder.deterministic_failure_message,
            "_required_read_paths": lambda context: PathResolver.required_read_paths(context, self.workspace),
            "_missing_required_read_paths": lambda context: PathResolver.missing_required_read_paths(context, self.workspace),
            "_partition_required_read_paths": lambda context: PathResolver.partition_required_read_paths(context, self.workspace),
            "_required_write_paths": PathResolver.required_write_paths,
            "_observed_read_paths": PathResolver.observed_read_paths,
            "_observed_write_paths": PathResolver.observed_write_paths,
            "_message_hash": self.artifact_writer.message_hash,
            "_memory_trace_enabled": self.artifact_writer.memory_trace_enabled,
            "_hash_payload": self.artifact_writer.hash_payload,
            "_append_memory_event": self.artifact_writer.append_memory_event,
            "_emit_memory_traces": self.artifact_writer.emit_memory_traces,
            "_tool_replay_key": self.artifact_writer.tool_replay_key,
            "_tool_result_path": self.artifact_writer.tool_result_path,
            "_load_replay_tool_result": self.artifact_writer.load_replay_tool_result,
            "_persist_tool_result": self.artifact_writer.persist_tool_result,
            "_state_delta_from_tool_calls": lambda context, turn: turn_executor_ops.state_delta_from_tool_calls(context, turn),
            "_synthesize_required_status_tool_call": lambda turn, context: turn_executor_ops.synthesize_required_status_tool_call(turn, context),
        }
        target = delegated.get(name)
        if target is not None:
            return target
        raise AttributeError(name)

    async def execute_turn(
        self,
        issue: IssueConfig,
        role: RoleConfig,
        model_client: Any,
        toolbox: Any,
        context: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> TurnResult:
        return await turn_executor_ops.execute_turn(self, issue, role, model_client, toolbox, context, system_prompt)

    @staticmethod
    def _runtime_tokens_payload(turn: ExecutionTurn) -> Any:
        return turn_executor_ops.runtime_tokens_payload(turn)

    async def _prepare_messages(
        self,
        issue: IssueConfig,
        role: RoleConfig,
        context: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        return await self.message_builder.prepare_messages(
            issue=issue,
            role=role,
            context=context,
            system_prompt=system_prompt,
        )

    def _parse_response(
        self,
        response: Any,
        issue_id: str,
        role_name: str,
        context: Dict[str, Any],
    ) -> ExecutionTurn:
        return self.response_parser.parse_response(
            response=response,
            issue_id=issue_id,
            role_name=role_name,
            context=context,
        )

    async def _execute_tools(
        self,
        turn: ExecutionTurn,
        toolbox: Any,
        context: Dict[str, Any],
        issue: Optional[IssueConfig] = None,
    ) -> None:
        await self.tool_dispatcher.execute_tools(
            turn=turn,
            toolbox=toolbox,
            context=context,
            issue=issue,
        )

    def _write_turn_artifact(
        self,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        filename: str,
        content: str,
    ) -> None:
        self.artifact_writer.write_turn_artifact(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            filename=filename,
            content=content,
        )

    def _write_turn_checkpoint(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        prompt_hash: str,
        selected_model: Any,
        tool_calls: List[Dict[str, Any]],
        state_delta: Dict[str, Any],
        prompt_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.artifact_writer.write_turn_checkpoint(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            prompt_hash=prompt_hash,
            selected_model=selected_model,
            tool_calls=tool_calls,
            state_delta=state_delta,
            prompt_metadata=prompt_metadata,
        )

    def _validate_preconditions(self, issue: IssueConfig, role: RoleConfig, context: Dict[str, Any]) -> None:
        if "session_id" not in context:
            raise ValueError("session_id required in context")

        allowed_types = role.capabilities.get("issue_types")
        if allowed_types is None:
            allowed_types = ["issue", "story", "bug", "task"]

        current_type = issue.type.value if hasattr(issue.type, "value") else str(issue.type)
        if current_type not in allowed_types:
            raise ValueError(f"Role {role.name} cannot handle {current_type} issues (Allowed: {allowed_types})")

        current_status = CardStatus(issue.status)
        if current_status not in [
            CardStatus.READY,
            CardStatus.IN_PROGRESS,
            CardStatus.CODE_REVIEW,
            CardStatus.AWAITING_GUARD_REVIEW,
        ]:
            raise StateMachineError(f"Issue {issue.id} in status {current_status} cannot be executed")


class ToolValidationError(Exception):
    """Tool call validation failed."""

    def __init__(self, violations: List[str]):
        self.violations = violations
        super().__init__(f"Tool validation failed: {violations}")


class ModelTimeoutError(Exception):
    """Model request timed out."""


__all__ = [
    "ContractValidator",
    "CorrectivePromptBuilder",
    "MessageBuilder",
    "ModelTimeoutError",
    "PathResolver",
    "ResponseParser",
    "ToolDispatcher",
    "ToolValidationError",
    "TurnArtifactWriter",
    "TurnExecutor",
    "TurnResult",
]
