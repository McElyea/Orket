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
from datetime import datetime, UTC
from pathlib import Path

from orket.schema import IssueConfig, CardStatus, RoleConfig
from orket.domain.state_machine import StateMachine, StateMachineError, WaitReason
from orket.domain.execution import ExecutionTurn, ToolCall
from orket.logging import log_event
from orket.services.tool_gate import ToolGate


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
        workspace: Path
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

        try:
            # 1. Validate we can execute this turn
            self._validate_preconditions(issue, role, context)

            # 2. Prepare the prompt
            messages = await self._prepare_messages(issue, role, context, system_prompt)

            # 3. Call LLM (async)
            log_event(
                "turn_start",
                {"issue_id": issue_id, "role": role_name},
                self.workspace
            )

            response = await model_client.complete(messages)

            # 4. Parse response into ExecutionTurn
            turn = self._parse_response(
                response=response,
                issue_id=issue_id,
                role_name=role_name
            )

            # 5. Execute tool calls (if any)
            if turn.tool_calls:
                await self._execute_tools(turn, toolbox, context)

            # 6. Log success
            log_event(
                "turn_complete",
                {
                    "issue_id": issue_id,
                    "role": role_name,
                    "tool_calls": len(turn.tool_calls),
                    "tokens": turn.tokens_used
                },
                self.workspace
            )

            return TurnResult.succeeded(turn)

        except StateMachineError as e:
            # State transition violation - don't retry
            log_event(
                "turn_failed",
                {"issue_id": issue_id, "error": str(e), "type": "state_violation"},
                self.workspace
            )
            return TurnResult.failed(f"State violation: {e}", should_retry=False)

        except ToolValidationError as e:
            # Tool call violation - can retry
            log_event(
                "turn_failed",
                {"issue_id": issue_id, "error": str(e), "type": "tool_violation"},
                self.workspace
            )
            return TurnResult.governance_violation(e.violations)

        except ModelTimeoutError as e:
            # Transient error - should retry
            log_event(
                "turn_failed",
                {"issue_id": issue_id, "error": str(e), "type": "timeout"},
                self.workspace
            )
            return TurnResult.failed(str(e), should_retry=True)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError, AttributeError) as e:
            # Unexpected error - log with traceback and don't retry
            import traceback
            log_event(
                "turn_failed",
                {
                    "issue_id": issue_id,
                    "error": str(e),
                    "type": type(e).__name__,
                    "traceback": traceback.format_exc()
                },
                self.workspace
            )
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
        if current_status not in [CardStatus.READY, CardStatus.IN_PROGRESS, CardStatus.CODE_REVIEW]:
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
        """
        Prepare message history for LLM.

        Args:
            issue: Issue configuration
            role: Role configuration
            context: Execution context
            system_prompt: Optional system prompt override

        Returns:
            List of messages in LLM format
        """
        messages = []

        # System message with role persona
        messages.append({
            "role": "system",
            "content": system_prompt or role.prompt or role.description
        })

        # Add issue context
        messages.append({
            "role": "user",
            "content": f"Issue {issue.id}: {issue.name}\n\nType: {issue.type}\nPriority: {issue.priority}"
        })

        # Add any history (from context)
        if "history" in context:
            messages.extend(context["history"])

        return messages

    def _parse_response(
        self,
        response: Any, # Can be ModelResponse or dict
        issue_id: str,
        role_name: str
    ) -> ExecutionTurn:
        """
        Parse LLM response into ExecutionTurn.

        Args:
            response: LLM response
            issue_id: Issue ID
            role_name: Role name

        Returns:
            ExecutionTurn with parsed data
        """
        from orket.services.tool_parser import ToolParser
        
        content = getattr(response, "content", "") if not isinstance(response, dict) else response.get("content", "")
        raw_data = getattr(response, "raw", {}) if not isinstance(response, dict) else response
        
        # Parse tool calls using the standardized ToolParser
        parsed_calls = ToolParser.parse(content)
        
        tool_calls = []
        for pc in parsed_calls:
            tool_calls.append(ToolCall(
                tool=pc.get("tool"),
                args=pc.get("args", {}),
                result=None,
                error=None
            ))

        return ExecutionTurn(
            role=role_name,
            issue_id=issue_id,
            thought=None, # Thought extraction could be added here if needed
            content=content,
            tool_calls=tool_calls,
            tokens_used=raw_data.get("total_tokens", 0),
            timestamp=datetime.now(UTC),
            raw=raw_data
        )

    async def _execute_tools(
        self,
        turn: ExecutionTurn,
        toolbox: Any,
        context: Dict[str, Any]
    ) -> None:
        """
        Execute all tool calls in a turn.
        """
        violations = []
        roles = context.get("roles", [turn.role])

        for tool_call in turn.tool_calls:
            try:
                # --- MECHANICAL GOVERNANCE: Tool Gate Enforcement ---
                gate_violation = self.tool_gate.validate(
                    tool_name=tool_call.tool,
                    args=tool_call.args,
                    context=context,
                    roles=roles
                )
                
                if gate_violation:
                    violations.append(f"Governance Violation: {gate_violation}")
                    continue

                # Execute tool (toolbox handles path validation)
                result = await toolbox.execute(
                    tool_call.tool,
                    tool_call.args,
                    context
                )

                tool_call.result = result

                if not result.get("ok", False):
                    violations.append(
                        f"Tool {tool_call.tool} failed: {result.get('error')}"
                    )

            except (ValueError, TypeError, KeyError, RuntimeError, OSError, AttributeError) as e:
                tool_call.error = str(e)
                violations.append(f"Tool {tool_call.tool} error: {e}")

        if violations:
            raise ToolValidationError(violations)


class ToolValidationError(Exception):
    """Tool call validation failed."""

    def __init__(self, violations: List[str]):
        self.violations = violations
        super().__init__(f"Tool validation failed: {violations}")


class ModelTimeoutError(Exception):
    """Model request timed out."""
    pass
