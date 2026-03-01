"""
Turn Executor - The Reconstruction

Single Responsibility: Execute one agent turn with proper async I/O.

This replaces the 200-line god method in orket.py with a clean,
testable, async-native implementation.

Design Principles:
- Single Responsibility: One turn, one purpose
- Dependency Injection: All dependencies passed in
- Async Native: No blocking I/O
- Fail Fast: Specific exceptions, no bare except
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import time
import copy
import asyncio
import re

from orket.schema import IssueConfig, CardStatus, RoleConfig
from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.schema import WaitReason
from orket.domain.execution import ExecutionTurn, ToolCall
from orket.logging import log_event
from orket.core.policies.tool_gate import ToolGate
from orket.core.domain.verification_scope import parse_verification_scope
from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.services.tool_parser import ToolParser
from orket.application.workflows.turn_path_resolver import PathResolver
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.application.workflows.turn_corrective_prompt import CorrectivePromptBuilder
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.application.workflows.turn_contract_validator import ContractValidator


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
        """Turn executed successfully."""
        return cls(success=True, turn=turn)

    @classmethod
    def failed(cls, error: str, should_retry: bool = False) -> TurnResult:
        """Turn failed with error."""
        return cls(success=False, error=error, should_retry=should_retry)

    @classmethod
    def governance_violation(cls, violations: List[str]) -> TurnResult:
        """Turn violated governance rules."""
        return cls(
            success=False,
            error=f"Governance violations: {violations}",
            should_retry=True,
            violations=violations
        )


class TurnExecutor:
    """
    Executes a single agent turn.

    Responsibilities:
    1. Load issue configuration
    2. Validate state transitions
    3. Execute agent
    4. Validate tool calls
    5. Persist results

    Does NOT:
    - Loop over multiple issues (that's the job of TractionLoop)
    - Handle retries (that's the job of the caller)
    - Manage sessions (that's the job of SessionManager)
    """

    def __init__(
        self,
        state_machine: StateMachine,
        tool_gate: ToolGate,
        workspace: Path,
        middleware: Optional[TurnLifecycleInterceptors] = None,
    ):
        """
        Initialize turn executor.

        Args:
            state_machine: State machine for validation
            tool_gate: Tool gate for organizational policy enforcement
            workspace: Workspace root for logging
        """
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

    async def execute_turn(
        self,
        issue: IssueConfig,
        role: RoleConfig,
        model_client: Any,  # ModelClient interface
        toolbox: Any,  # ToolBox interface
        context: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> TurnResult:
        """
        Execute a single turn for an issue.

        Args:
            issue: Issue to work on
            role: Role executing the turn
            model_client: LLM client (async)
            toolbox: Tool execution environment
            context: Additional context (session_id, etc.)
            system_prompt: Optional system prompt override

        Returns:
            TurnResult with success/failure and turn data

        Raises:
            StateMachineError: If state transition is invalid
            ValueError: If required context is missing
        """
        issue_id = issue.id
        role_name = role.name
        session_id = context.get("session_id", "unknown-session")
        turn_index = int(context.get("turn_index", 0))
        turn_trace_id = f"{session_id}:{issue_id}:{role_name}:{turn_index}"
        started_at = time.perf_counter()
        current_turn: Optional[ExecutionTurn] = None

        def _emit_failure_traces(error: str, failure_type: str) -> None:
            self._append_memory_event(
                context,
                role_name=role_name,
                interceptor="on_turn_failure",
                decision_type=str(failure_type).strip() or "turn_failed",
            )
            self._emit_memory_traces(
                session_id=session_id,
                issue_id=issue_id,
                role_name=role_name,
                turn_index=turn_index,
                issue=issue,
                role=role,
                context=context,
                turn=current_turn,
                failure_reason=str(error or "").strip() or "turn_failed",
                failure_type=str(failure_type or "").strip() or "turn_failed",
            )

        try:
            if self._memory_trace_enabled(context):
                context["_memory_trace_events"] = []
            # 1. Validate we can execute this turn
            self._validate_preconditions(issue, role, context)

            # 2. Prepare the prompt
            messages = await self._prepare_messages(issue, role, context, system_prompt)
            messages, middleware_outcome = self.middleware.apply_before_prompt(
                messages,
                issue=issue,
                role=role,
                context=context,
            )
            if middleware_outcome and middleware_outcome.short_circuit:
                reason = middleware_outcome.reason or "short-circuit before_prompt"
                _emit_failure_traces(reason, "before_prompt_short_circuit")
                return TurnResult.failed(reason, should_retry=False)
            self._append_memory_event(
                context,
                role_name=role_name,
                interceptor="before_prompt",
                decision_type="prompt_ready",
            )
            prompt_hash = self._message_hash(messages)

            # 3. Call LLM (async)
            log_event(
                "turn_start",
                {
                    "issue_id": issue_id,
                    "role": role_name,
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "turn_trace_id": turn_trace_id,
                    "prompt_hash": prompt_hash,
                    "message_count": len(messages),
                    "selected_model": context.get("selected_model"),
                    "prompt_id": (context.get("prompt_metadata") or {}).get("prompt_id"),
                    "prompt_version": (context.get("prompt_metadata") or {}).get("prompt_version"),
                    "prompt_checksum": (context.get("prompt_metadata") or {}).get("prompt_checksum"),
                    "resolver_policy": (context.get("prompt_metadata") or {}).get("resolver_policy"),
                    "selection_policy": (context.get("prompt_metadata") or {}).get("selection_policy"),
                    "role_status": (context.get("prompt_metadata") or {}).get("role_status"),
                    "dialect_status": (context.get("prompt_metadata") or {}).get("dialect_status"),
                },
                self.workspace
            )
            self._write_turn_artifact(
                session_id,
                issue_id,
                role_name,
                turn_index,
                "messages.json",
                json.dumps(messages, indent=2, ensure_ascii=False),
            )
            self._write_turn_artifact(
                session_id,
                issue_id,
                role_name,
                turn_index,
                "prompt_layers.json",
                json.dumps(context.get("prompt_layers", {}), indent=2, ensure_ascii=False, default=str),
            )

            response = await model_client.complete(messages)
            response, middleware_outcome = self.middleware.apply_after_model(
                response,
                issue=issue,
                role=role,
                context=context,
            )
            if middleware_outcome and middleware_outcome.short_circuit:
                reason = middleware_outcome.reason or "short-circuit after_model"
                _emit_failure_traces(reason, "after_model_short_circuit")
                return TurnResult.failed(reason, should_retry=False)
            self._append_memory_event(
                context,
                role_name=role_name,
                interceptor="after_model",
                decision_type="model_response_processed",
            )
            response_content = getattr(response, "content", "") if not isinstance(response, dict) else response.get("content", "")
            response_raw = getattr(response, "raw", {}) if not isinstance(response, dict) else response
            self._write_turn_artifact(
                session_id,
                issue_id,
                role_name,
                turn_index,
                "model_response.txt",
                response_content or "",
            )
            self._write_turn_artifact(
                session_id,
                issue_id,
                role_name,
                turn_index,
                "model_response_raw.json",
                json.dumps(response_raw, indent=2, ensure_ascii=False, default=str),
            )

            # 4. Parse response into ExecutionTurn
            turn = self._parse_response(
                response=response,
                issue_id=issue_id,
                role_name=role_name,
                context=context,
            )
            current_turn = turn
            self._synthesize_required_status_tool_call(turn, context)
            contract_violations = self._collect_contract_violations(turn, role, context)
            if contract_violations:
                corrective_prompt = self._build_corrective_instruction(contract_violations, context)
                rule_fix_hints = self._rule_specific_fix_hints(contract_violations)
                retry_messages = copy.deepcopy(messages)
                retry_messages.append({"role": "user", "content": corrective_prompt})

                contract_reasons = [
                    str(item.get("reason", "")).strip()
                    for item in contract_violations
                    if str(item.get("reason", "")).strip()
                ]
                log_event(
                    "turn_corrective_reprompt",
                    {
                        "issue_id": issue_id,
                        "role": role_name,
                        "session_id": session_id,
                        "turn_index": turn_index,
                        "turn_trace_id": turn_trace_id,
                        "reason": contract_reasons[0] if len(contract_reasons) == 1 else "multiple_contracts_not_met",
                        "contract_reasons": contract_reasons,
                        "contract_violations": contract_violations,
                        "rule_fix_hints": rule_fix_hints,
                    },
                    self.workspace,
                )
                response = await model_client.complete(retry_messages)
                response, middleware_outcome = self.middleware.apply_after_model(
                    response,
                    issue=issue,
                    role=role,
                    context=context,
                )
                if middleware_outcome and middleware_outcome.short_circuit:
                    reason = middleware_outcome.reason or "short-circuit after_model"
                    _emit_failure_traces(reason, "after_model_short_circuit")
                    return TurnResult.failed(reason, should_retry=False)
                self._append_memory_event(
                    context,
                    role_name=role_name,
                    interceptor="after_model",
                    decision_type="model_response_reprompt_processed",
                )

                turn = self._parse_response(
                    response=response,
                    issue_id=issue_id,
                    role_name=role_name,
                    context=context,
                )
                current_turn = turn
                self._synthesize_required_status_tool_call(turn, context)
                contract_violations = self._collect_contract_violations(turn, role, context)
                if contract_violations:
                    contract_reasons = [
                        str(item.get("reason", "")).strip()
                        for item in contract_violations
                        if str(item.get("reason", "")).strip()
                    ]
                    primary_reason = contract_reasons[0] if contract_reasons else "contract_not_met"
                    log_event(
                        "turn_non_progress",
                        {
                            "issue_id": issue_id,
                            "role": role_name,
                            "session_id": session_id,
                            "turn_index": turn_index,
                            "turn_trace_id": turn_trace_id,
                            "reason": f"{primary_reason}_after_reprompt",
                            "contract_reasons": contract_reasons,
                            "contract_violations": contract_violations,
                        },
                        self.workspace,
                    )
                    _emit_failure_traces(primary_reason, "contract_violation")
                    return TurnResult.failed(
                        self._deterministic_failure_message(primary_reason),
                        should_retry=False,
                    )

            self._write_turn_artifact(
                session_id,
                issue_id,
                role_name,
                turn_index,
                "parsed_tool_calls.json",
                json.dumps(
                    [{"tool": t.tool, "args": t.args} for t in turn.tool_calls],
                    indent=2,
                    ensure_ascii=False,
                ),
            )
            self._write_turn_checkpoint(
                session_id=session_id,
                issue_id=issue_id,
                role_name=role_name,
                turn_index=turn_index,
                prompt_hash=prompt_hash,
                selected_model=context.get("selected_model"),
                tool_calls=[{"tool": t.tool, "args": t.args} for t in turn.tool_calls],
                state_delta=self._state_delta_from_tool_calls(context, turn),
                prompt_metadata=context.get("prompt_metadata"),
            )

            # 5. Execute tool calls (if any)
            if turn.tool_calls:
                await self._execute_tools(turn, toolbox, context, issue=issue)
            else:
                log_event(
                    "turn_no_tool_calls",
                    {
                        "issue_id": issue_id,
                        "role": role_name,
                        "session_id": session_id,
                        "turn_index": turn_index,
                        "turn_trace_id": turn_trace_id,
                        "response_preview": (turn.content or "")[:240],
                    },
                    self.workspace,
                )

            # 6. Log success
            log_event(
                "turn_complete",
                {
                    "issue_id": issue_id,
                    "role": role_name,
                    "tool_calls": len(turn.tool_calls),
                    "tokens": self._runtime_tokens_payload(turn),
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "turn_trace_id": turn_trace_id,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                },
                self.workspace
            )
            self._emit_memory_traces(
                session_id=session_id,
                issue_id=issue_id,
                role_name=role_name,
                turn_index=turn_index,
                issue=issue,
                role=role,
                context=context,
                turn=turn,
            )

            return TurnResult.succeeded(turn)

        except StateMachineError as e:
            self.middleware.apply_on_turn_failure(e, issue=issue, role=role, context=context)
            # State transition violation - don't retry
            log_event(
                "turn_failed",
                {
                    "issue_id": issue_id,
                    "error": str(e),
                    "type": "state_violation",
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "turn_trace_id": turn_trace_id,
                },
                self.workspace
            )
            _emit_failure_traces(str(e), "state_violation")
            return TurnResult.failed(f"State violation: {e}", should_retry=False)

        except ToolValidationError as e:
            self.middleware.apply_on_turn_failure(e, issue=issue, role=role, context=context)
            # Tool call violation - can retry
            log_event(
                "turn_failed",
                {
                    "issue_id": issue_id,
                    "error": str(e),
                    "type": "tool_violation",
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "turn_trace_id": turn_trace_id,
                },
                self.workspace
            )
            _emit_failure_traces(str(e), "tool_violation")
            return TurnResult.governance_violation(e.violations)

        except ModelTimeoutError as e:
            self.middleware.apply_on_turn_failure(e, issue=issue, role=role, context=context)
            # Transient error - should retry
            log_event(
                "turn_failed",
                {
                    "issue_id": issue_id,
                    "error": str(e),
                    "type": "timeout",
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "turn_trace_id": turn_trace_id,
                },
                self.workspace
            )
            _emit_failure_traces(str(e), "timeout")
            return TurnResult.failed(str(e), should_retry=True)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError, AttributeError) as e:
            self.middleware.apply_on_turn_failure(e, issue=issue, role=role, context=context)
            # Unexpected error - log with traceback and don't retry
            import traceback
            log_event(
                "turn_failed",
                {
                    "issue_id": issue_id,
                    "error": str(e),
                    "type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "turn_trace_id": turn_trace_id,
                },
                self.workspace
            )
            _emit_failure_traces(str(e), type(e).__name__)
            return TurnResult.failed(f"Unexpected error: {e}", should_retry=False)

    def _validate_preconditions(
        self,
        issue: IssueConfig,
        role: RoleConfig,
        context: Dict[str, Any]
    ) -> None:
        """
        Validate that we can execute this turn.

        Raises:
            ValueError: If preconditions not met
            StateMachineError: If state transition invalid
        """
        # Required context
        if "session_id" not in context:
            raise ValueError("session_id required in context")

        # Check role can execute this issue type
        allowed_types = role.capabilities.get("issue_types")
        if allowed_types is None:
            allowed_types = ["issue", "story", "bug", "task"]
            
        current_type = issue.type.value if hasattr(issue.type, "value") else str(issue.type)
        if current_type not in allowed_types:
            raise ValueError(
                f"Role {role.name} cannot handle {current_type} issues (Allowed: {allowed_types})"
            )

        # Validate current status allows execution
        current_status = CardStatus(issue.status)
        if current_status not in [
            CardStatus.READY,
            CardStatus.IN_PROGRESS,
            CardStatus.CODE_REVIEW,
            CardStatus.AWAITING_GUARD_REVIEW,
        ]:
            raise StateMachineError(
                f"Issue {issue.id} in status {current_status} cannot be executed"
            )

    async def _prepare_messages(
        self,
        issue: IssueConfig,
        role: RoleConfig,
        context: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        return await self.message_builder.prepare_messages(
            issue=issue,
            role=role,
            context=context,
            system_prompt=system_prompt,
        )

    @staticmethod
    def _runtime_tokens_payload(turn: ExecutionTurn) -> Any:
        raw_data = turn.raw if isinstance(turn.raw, dict) else {}
        usage = raw_data.get("usage") if isinstance(raw_data.get("usage"), dict) else {}
        timings = raw_data.get("timings") if isinstance(raw_data.get("timings"), dict) else {}

        prompt_tokens = usage.get("prompt_tokens", raw_data.get("input_tokens"))
        output_tokens = usage.get("completion_tokens", raw_data.get("output_tokens"))
        total_tokens = usage.get("total_tokens", raw_data.get("total_tokens", turn.tokens_used))

        prompt_ms = timings.get("prompt_ms")
        predicted_ms = timings.get("predicted_ms")

        has_tokens = isinstance(prompt_tokens, int) and isinstance(output_tokens, int)
        has_timings = isinstance(prompt_ms, (int, float)) and isinstance(predicted_ms, (int, float))

        status = "OK"
        if not has_tokens and not has_timings:
            status = "TOKEN_AND_TIMING_UNAVAILABLE"
        elif not has_tokens:
            status = "TOKEN_COUNT_UNAVAILABLE"
        elif not has_timings:
            status = "TIMING_UNAVAILABLE"

        if not isinstance(total_tokens, int):
            total_tokens = turn.tokens_used if isinstance(turn.tokens_used, int) else None

        return {
            "status": status,
            "prompt_tokens": prompt_tokens if isinstance(prompt_tokens, int) else None,
            "output_tokens": output_tokens if isinstance(output_tokens, int) else None,
            "total_tokens": total_tokens,
            "prompt_ms": float(prompt_ms) if isinstance(prompt_ms, (int, float)) else None,
            "predicted_ms": float(predicted_ms) if isinstance(predicted_ms, (int, float)) else None,
        }

    def _parse_response(
        self,
        response: Any, # Can be ModelResponse or dict
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

    def _resolve_skill_tool_binding(self, context: Dict[str, Any], tool_name: str) -> Dict[str, Any] | None:
        return self.tool_dispatcher.resolve_skill_tool_binding(context, tool_name)

    def _missing_required_permissions(self, binding: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        return self.tool_dispatcher.missing_required_permissions(binding, context)

    def _permission_values(self, values: Any) -> set[str]:
        return self.tool_dispatcher.permission_values(values)

    def _runtime_limit_violations(self, binding: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        return self.tool_dispatcher.runtime_limit_violations(binding, context)

    def _as_positive_float(self, value: Any) -> float | None:
        return self.tool_dispatcher.as_positive_float(value)

    def _collect_contract_violations(
        self,
        turn: ExecutionTurn,
        role: RoleConfig,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return self.contract_validator.collect_contract_violations(turn, role, context)

    def _build_corrective_instruction(
        self,
        violations: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        return self.corrective_prompt_builder.build_corrective_instruction(violations, context)

    def _rule_specific_fix_hints(self, violations: List[Dict[str, Any]]) -> List[str]:
        return self.corrective_prompt_builder.rule_specific_fix_hints(violations)

    def _hint_for_rule_id(self, rule_id: str, evidence: str) -> str:
        return self.corrective_prompt_builder.hint_for_rule_id(rule_id, evidence)

    def _deterministic_failure_message(self, reason: str) -> str:
        return self.corrective_prompt_builder.deterministic_failure_message(reason)

    def _required_read_paths(self, context: Dict[str, Any]) -> List[str]:
        return PathResolver.required_read_paths(context, self.workspace)

    def _missing_required_read_paths(self, context: Dict[str, Any]) -> List[str]:
        return PathResolver.missing_required_read_paths(context, self.workspace)

    def _partition_required_read_paths(self, context: Dict[str, Any]) -> tuple[List[str], List[str]]:
        return PathResolver.partition_required_read_paths(context, self.workspace)

    def _required_write_paths(self, context: Dict[str, Any]) -> List[str]:
        return PathResolver.required_write_paths(context)

    def _observed_read_paths(self, turn: ExecutionTurn) -> List[str]:
        return PathResolver.observed_read_paths(turn)

    def _observed_write_paths(self, turn: ExecutionTurn) -> List[str]:
        return PathResolver.observed_write_paths(turn)

    def _progress_contract_diagnostics(
        self,
        turn: ExecutionTurn,
        role: RoleConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self.contract_validator.progress_contract_diagnostics(turn, role, context)

    def _meets_progress_contract(self, turn: ExecutionTurn, role: RoleConfig, context: Dict[str, Any]) -> bool:
        return self.contract_validator.meets_progress_contract(turn, role, context)

    def _meets_write_path_contract(self, turn: ExecutionTurn, context: Dict[str, Any]) -> bool:
        return self.contract_validator.meets_write_path_contract(turn, context)

    def _meets_guard_rejection_payload_contract(self, turn: ExecutionTurn, context: Dict[str, Any]) -> bool:
        return self.contract_validator.meets_guard_rejection_payload_contract(turn, context)

    def _meets_read_path_contract(self, turn: ExecutionTurn, context: Dict[str, Any]) -> bool:
        return self.contract_validator.meets_read_path_contract(turn, context)

    def _meets_architecture_decision_contract(self, turn: ExecutionTurn, context: Dict[str, Any]) -> bool:
        return self.contract_validator.meets_architecture_decision_contract(turn, context)

    def _parse_architecture_decision_payload(self, raw_content: str) -> Optional[Dict[str, Any]]:
        return self.contract_validator.parse_architecture_decision_payload(raw_content)

    def _hallucination_scope_diagnostics(self, turn: ExecutionTurn, context: Dict[str, Any]) -> Dict[str, Any]:
        return self.contract_validator.hallucination_scope_diagnostics(turn, context)

    def _security_scope_diagnostics(self, turn: ExecutionTurn, context: Dict[str, Any]) -> Dict[str, Any]:
        return self.contract_validator.security_scope_diagnostics(turn, context)

    def _consistency_scope_diagnostics(self, turn: ExecutionTurn, context: Dict[str, Any]) -> Dict[str, Any]:
        return self.contract_validator.consistency_scope_diagnostics(turn, context)

    def _non_json_residue(self, content: str) -> str:
        return self.response_parser.non_json_residue(content)

    def _extract_guard_review_payload(self, content: str) -> Dict[str, Any]:
        return self.response_parser.extract_guard_review_payload(content)

    def _message_hash(self, messages: List[Dict[str, str]]) -> str:
        return self.artifact_writer.message_hash(messages)

    def _memory_trace_enabled(self, context: Dict[str, Any]) -> bool:
        return self.artifact_writer.memory_trace_enabled(context)

    def _hash_payload(self, payload: Any) -> str:
        return self.artifact_writer.hash_payload(payload)

    def _append_memory_event(
        self,
        context: Dict[str, Any],
        *,
        role_name: str,
        interceptor: str,
        decision_type: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        guardrails_triggered: Optional[List[str]] = None,
        retrieval_event_ids: Optional[List[str]] = None,
    ) -> None:
        self.artifact_writer.append_memory_event(
            context,
            role_name=role_name,
            interceptor=interceptor,
            decision_type=decision_type,
            tool_calls=tool_calls,
            guardrails_triggered=guardrails_triggered,
            retrieval_event_ids=retrieval_event_ids,
        )

    def _emit_memory_traces(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        issue: IssueConfig,
        role: RoleConfig,
        context: Dict[str, Any],
        turn: Optional[ExecutionTurn] = None,
        failure_reason: str = "",
        failure_type: str = "",
    ) -> None:
        self.artifact_writer.emit_memory_traces(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            issue=issue,
            role=role,
            context=context,
            turn=turn,
            failure_reason=failure_reason,
            failure_type=failure_type,
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

    def _state_delta_from_tool_calls(self, context: Dict[str, Any], turn: ExecutionTurn) -> Dict[str, Any]:
        current = context.get("current_status")
        requested = None
        for call in turn.tool_calls:
            if call.tool == "update_issue_status":
                requested = call.args.get("status")
                break
        return {"from": current, "to": requested}

    def _synthesize_required_status_tool_call(self, turn: ExecutionTurn, context: Dict[str, Any]) -> None:
        role_names = {
            str(value).strip().lower() for value in (context.get("roles") or [context.get("role")]) if str(value).strip()
        }
        required_tools = {
            str(tool).strip() for tool in (context.get("required_action_tools") or []) if str(tool).strip()
        }
        if "update_issue_status" not in required_tools:
            return
        if any(str(call.tool or "").strip() == "update_issue_status" for call in (turn.tool_calls or [])):
            return

        required_statuses = [
            str(status).strip().lower()
            for status in (context.get("required_statuses") or [])
            if str(status).strip()
        ]
        required_status: Optional[str] = None
        if len(required_statuses) == 1:
            required_status = required_statuses[0]
        elif (
            "integrity_guard" in role_names
            and {"done", "blocked"}.issubset(set(required_statuses))
            and bool(context.get("runtime_verifier_ok")) is True
        ):
            required_status = "done"
        if not required_status:
            return
        if required_status == "blocked":
            return

        turn.tool_calls.append(
            ToolCall(
                tool="update_issue_status",
                args={"status": required_status},
                result=None,
                error=None,
            )
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

    def _tool_replay_key(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        return self.artifact_writer.tool_replay_key(tool_name, tool_args)

    def _tool_result_path(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Path:
        return self.artifact_writer.tool_result_path(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            tool_name=tool_name,
            tool_args=tool_args,
        )

    def _load_replay_tool_result(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        tool_name: str,
        tool_args: Dict[str, Any],
        resume_mode: bool,
    ) -> Optional[Dict[str, Any]]:
        return self.artifact_writer.load_replay_tool_result(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            tool_name=tool_name,
            tool_args=tool_args,
            resume_mode=resume_mode,
        )

    def _persist_tool_result(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        tool_name: str,
        tool_args: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        self.artifact_writer.persist_tool_result(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            tool_name=tool_name,
            tool_args=tool_args,
            result=result,
        )


class ToolValidationError(Exception):
    """Tool call validation failed."""

    def __init__(self, violations: List[str]):
        self.violations = violations
        super().__init__(f"Tool validation failed: {violations}")


class ModelTimeoutError(Exception):
    """Model request timed out."""
    pass
