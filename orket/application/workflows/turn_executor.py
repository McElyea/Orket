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
import json
import time
import hashlib
import copy
import asyncio

from orket.schema import IssueConfig, CardStatus, RoleConfig
from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.schema import WaitReason
from orket.domain.execution import ExecutionTurn, ToolCall
from orket.logging import log_event
from orket.core.policies.tool_gate import ToolGate
from orket.naming import sanitize_name
from orket.application.middleware import MiddlewarePipeline


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
        middleware: Optional[MiddlewarePipeline] = None,
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
        self.middleware = middleware or MiddlewarePipeline([])

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

        try:
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
                return TurnResult.failed(reason, should_retry=False)
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
                return TurnResult.failed(reason, should_retry=False)
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
            contract_violations = self._collect_contract_violations(turn, role, context)
            if contract_violations:
                corrective_prompt = self._build_corrective_instruction(contract_violations, context)
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
                    return TurnResult.failed(reason, should_retry=False)

                turn = self._parse_response(
                    response=response,
                    issue_id=issue_id,
                    role_name=role_name,
                    context=context,
                )
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
                    "tokens": turn.tokens_used,
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "turn_trace_id": turn_trace_id,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                },
                self.workspace
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

        # Add stable, structured execution context for deterministic routing and dependency awareness.
        execution_context = {
            "issue_id": context.get("issue_id", issue.id),
            "seat": context.get("role", role.name),
            "status": context.get("current_status"),
            "dependency_context": context.get("dependency_context", {}),
            "required_action_tools": context.get("required_action_tools", []),
            "required_statuses": context.get("required_statuses", []),
            "required_read_paths": context.get("required_read_paths", []),
            "required_write_paths": context.get("required_write_paths", []),
            "stage_gate_mode": context.get("stage_gate_mode"),
            "runtime_verifier_ok": context.get("runtime_verifier_ok"),
            "architecture_mode": context.get("architecture_mode"),
            "frontend_framework_mode": context.get("frontend_framework_mode"),
            "architecture_decision_required": bool(context.get("architecture_decision_required")),
            "architecture_decision_path": context.get("architecture_decision_path"),
            "architecture_forced_pattern": context.get("architecture_forced_pattern"),
            "frontend_framework_forced": context.get("frontend_framework_forced"),
            "prompt_metadata": context.get("prompt_metadata", {}),
        }
        messages.append({
            "role": "user",
            "content": f"Execution Context JSON:\n{json.dumps(execution_context, sort_keys=True)}"
        })

        required_action_tools = [str(t) for t in (context.get("required_action_tools") or []) if t]
        required_statuses = [str(s).strip().lower() for s in (context.get("required_statuses") or []) if s]
        required_read_paths = [str(p).strip() for p in (context.get("required_read_paths") or []) if str(p).strip()]
        required_write_paths = [str(p).strip() for p in (context.get("required_write_paths") or []) if str(p).strip()]
        if required_action_tools or required_statuses:
            contract_lines = []
            if required_action_tools:
                contract_lines.append(f"- Required tool calls this turn: {', '.join(required_action_tools)}")
            if required_statuses:
                contract_lines.append(
                    f"- Required update_issue_status.status values: {', '.join(required_statuses)}"
                )
                contract_lines.append(
                    "- If you choose status=blocked, include wait_reason: resource|dependency|review|input|system."
                )
            contract_lines.append("- You must include all required tool calls in this same response.")
            contract_lines.append("- A response containing only get_issue_context/add_issue_comment is invalid.")
            messages.append(
                {
                    "role": "user",
                    "content": "Turn Success Contract:\n" + "\n".join(contract_lines),
                }
            )

        if required_write_paths:
            write_lines = [
                "- Required write_file paths this turn:",
                *[f"  - {path}" for path in required_write_paths],
                "- Use workspace-relative paths exactly as listed.",
            ]
            messages.append(
                {
                    "role": "user",
                    "content": "Write Path Contract:\n" + "\n".join(write_lines),
                }
            )

        if required_read_paths:
            read_lines = [
                "- Required read_file paths this turn:",
                *[f"  - {path}" for path in required_read_paths],
                "- Do not use placeholder or absolute paths outside the workspace.",
            ]
            messages.append(
                {
                    "role": "user",
                    "content": "Read Path Contract:\n" + "\n".join(read_lines),
                }
            )

        if bool(context.get("architecture_decision_required")):
            mode = str(context.get("architecture_mode", "architect_decides"))
            decision_path = str(context.get("architecture_decision_path", "agent_output/design.txt"))
            forced_pattern = str(context.get("architecture_forced_pattern", "") or "").strip().lower()
            forced_frontend_framework = str(context.get("frontend_framework_forced", "") or "").strip().lower()
            allowed_frontend_frameworks = [
                str(v).strip().lower()
                for v in (context.get("frontend_framework_allowed") or ["vue", "react", "angular"])
                if str(v).strip()
            ]
            allowed_patterns = [
                str(v).strip().lower()
                for v in (context.get("architecture_allowed_patterns") or ["monolith", "microservices"])
                if str(v).strip()
            ]
            lines = [
                f"- Write architecture decision JSON to path: {decision_path}",
                f"- recommendation must be one of: {', '.join(allowed_patterns)}",
                "- confidence must be a number between 0 and 1",
                "- evidence must include keys: estimated_domains, external_integrations, independent_scaling_needs, deployment_complexity, team_parallelism, operational_maturity",
                f"- active architecture mode: {mode}",
                f"- frontend_framework should be one of: {', '.join(allowed_frontend_frameworks)}",
            ]
            if forced_pattern:
                lines.append(f"- recommendation MUST equal: {forced_pattern}")
            if forced_frontend_framework:
                lines.append(f"- frontend_framework MUST equal: {forced_frontend_framework}")
            messages.append(
                {
                    "role": "user",
                    "content": "Architecture Decision Contract:\n" + "\n".join(lines),
                }
            )

        if str(context.get("stage_gate_mode", "")).strip().lower() == "review_required":
            runtime_ok = context.get("runtime_verifier_ok")
            runtime_line = "- Runtime verifier result unavailable."
            if runtime_ok is True:
                runtime_line = "- Runtime verifier passed for this issue."
            elif runtime_ok is False:
                runtime_line = "- Runtime verifier failed for this issue."
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Guard Rejection Contract:\n"
                        "- If you set update_issue_status.status to blocked, include a second JSON object in the same response.\n"
                        '- Required payload schema: {"rationale":"...", "violations":[...], "remediation_actions":[...]}.\n'
                        "- rationale must be non-empty.\n"
                        "- violations must contain at least one concrete defect.\n"
                        "- remediation_actions must contain at least one concrete action.\n"
                        f"{runtime_line}\n"
                        "- If runtime verifier passed and no concrete defect is present, choose status=done."
                    ),
                }
            )

        # Add any history (from context)
        if "history" in context:
            messages.extend(context["history"])

        return messages

    def _parse_response(
        self,
        response: Any, # Can be ModelResponse or dict
        issue_id: str,
        role_name: str,
        context: Dict[str, Any],
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
        from orket.application.services.tool_parser import ToolParser
        
        content = getattr(response, "content", "") if not isinstance(response, dict) else response.get("content", "")
        raw_data = getattr(response, "raw", {}) if not isinstance(response, dict) else response
        
        parser_diag: List[Dict[str, Any]] = []

        def capture(stage: str, data: Dict[str, Any]) -> None:
            parser_diag.append({"stage": stage, "data": data})

        # Parse tool calls using the standardized ToolParser
        parsed_calls = ToolParser.parse(content, diagnostics=capture)
        session_id = context.get("session_id", "unknown-session")
        turn_index = int(context.get("turn_index", 0))
        for diag in parser_diag:
            log_event(
                "tool_parser_diagnostic",
                {
                    "issue_id": issue_id,
                    "role": role_name,
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "stage": diag["stage"],
                    "details": diag["data"],
                },
                self.workspace,
            )
        self._write_turn_artifact(
            session_id,
            issue_id,
            role_name,
            turn_index,
            "tool_parser_diagnostics.json",
            json.dumps(parser_diag, indent=2, ensure_ascii=False),
        )
        
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
        context: Dict[str, Any],
        issue: Optional[IssueConfig] = None,
    ) -> None:
        """
        Execute all tool calls in a turn.
        """
        violations = []
        roles = context.get("roles", [turn.role])
        session_id = context.get("session_id", "unknown-session")
        turn_index = int(context.get("turn_index", 0))
        approval_required_tools = {
            str(tool).strip()
            for tool in (context.get("approval_required_tools") or [])
            if str(tool).strip()
        }
        request_writer = context.get("create_pending_gate_request")

        for tool_call in turn.tool_calls:
            try:
                middleware_outcome = self.middleware.apply_before_tool(
                    tool_call.tool,
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

                # --- MECHANICAL GOVERNANCE: Tool Gate Enforcement ---
                gate_violation = self.tool_gate.validate(
                    tool_name=tool_call.tool,
                    args=tool_call.args,
                    context=context,
                    roles=roles
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

                if tool_call.tool in approval_required_tools:
                    request_id = None
                    if callable(request_writer):
                        maybe_request = request_writer(
                            tool_name=tool_call.tool,
                            tool_args=tool_call.args,
                        )
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
                    violations.append(
                        f"Approval required for tool '{tool_call.tool}' before execution."
                    )
                    continue

                # Execute tool (toolbox handles path validation)
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
                replay_result = self._load_replay_tool_result(
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
                    result = await toolbox.execute(
                        tool_call.tool,
                        tool_call.args,
                        context
                    )
                result = self.middleware.apply_after_tool(
                    tool_call.tool,
                    tool_call.args,
                    result,
                    issue=issue,
                    role_name=turn.role,
                    context=context,
                )

                tool_call.result = result
                self._persist_tool_result(
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
                    violations.append(
                        f"Tool {tool_call.tool} failed: {result.get('error')}"
                    )

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
            raise ToolValidationError(violations)

    def _collect_contract_violations(
        self,
        turn: ExecutionTurn,
        role: RoleConfig,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        violations: List[Dict[str, Any]] = []

        progress_diag = self._progress_contract_diagnostics(turn, role, context)
        if not progress_diag.get("ok", False):
            violations.append(
                {
                    "reason": "progress_contract_not_met",
                    "required_action_tools": progress_diag.get("required_action_tools", []),
                    "required_statuses": progress_diag.get("required_statuses", []),
                    "observed_tools": progress_diag.get("observed_tools", []),
                    "missing_required_tools": progress_diag.get("missing_required_tools", []),
                    "observed_statuses": progress_diag.get("observed_statuses", []),
                }
            )

        if not self._meets_write_path_contract(turn, context):
            violations.append(
                {
                    "reason": "write_path_contract_not_met",
                    "required_write_paths": self._required_write_paths(context),
                    "observed_write_paths": self._observed_write_paths(turn),
                }
            )

        if not self._meets_read_path_contract(turn, context):
            violations.append(
                {
                    "reason": "read_path_contract_not_met",
                    "required_read_paths": self._required_read_paths(context),
                    "observed_read_paths": self._observed_read_paths(turn),
                }
            )

        if not self._meets_architecture_decision_contract(turn, context):
            violations.append(
                {
                    "reason": "architecture_decision_contract_not_met",
                    "architecture_mode": context.get("architecture_mode"),
                    "architecture_decision_path": context.get("architecture_decision_path"),
                }
            )

        if not self._meets_guard_rejection_payload_contract(turn, context):
            violations.append(
                {
                    "reason": "guard_rejection_payload_contract_not_met",
                    "stage_gate_mode": context.get("stage_gate_mode"),
                }
            )

        return violations

    def _build_corrective_instruction(
        self,
        violations: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        lines = [
            "Corrective instruction: previous response violated deterministic turn contracts.",
            "Return JSON tool-call blocks only and satisfy all required contracts in this same response.",
        ]

        reason_set = {
            str(item.get("reason", "")).strip()
            for item in violations
            if str(item.get("reason", "")).strip()
        }

        if "progress_contract_not_met" in reason_set:
            required_action_tools = [
                str(t) for t in (context.get("required_action_tools") or []) if str(t).strip()
            ]
            required_statuses = [
                str(s).strip().lower()
                for s in (context.get("required_statuses") or [])
                if str(s).strip()
            ]
            if required_action_tools:
                lines.append(f"- Required tools this turn: {', '.join(required_action_tools)}.")
            if required_statuses:
                lines.append(
                    "- Required update_issue_status values: "
                    + ", ".join(required_statuses)
                    + "."
                )
                if "blocked" in required_statuses:
                    lines.append(
                        "- If status=blocked, include wait_reason in: resource|dependency|review|input|system."
                    )

        if "write_path_contract_not_met" in reason_set:
            required_write_paths = self._required_write_paths(context)
            if required_write_paths:
                lines.append("- Required write_file paths:")
                for path in required_write_paths:
                    lines.append(f"  - {path}")

        if "read_path_contract_not_met" in reason_set:
            required_read_paths = self._required_read_paths(context)
            if required_read_paths:
                lines.append("- Required read_file paths:")
                for path in required_read_paths:
                    lines.append(f"  - {path}")

        if "architecture_decision_contract_not_met" in reason_set:
            lines.append(
                "- Architecture decision JSON is required at the configured architecture_decision_path "
                "with recommendation, confidence (0..1), and full evidence keys."
            )

        if "guard_rejection_payload_contract_not_met" in reason_set:
            lines.append(
                "- If update_issue_status.status=blocked, include JSON payload keys: "
                "rationale (non-empty), violations (non-empty list), remediation_actions (non-empty list)."
            )

        required_read_paths = self._required_read_paths(context)
        required_write_paths = self._required_write_paths(context)
        required_statuses = [
            str(s).strip().lower()
            for s in (context.get("required_statuses") or [])
            if str(s).strip()
        ]
        if required_read_paths or required_write_paths or required_statuses:
            lines.append("- Required-call template (emit blocks like these in this same response):")
            for path in required_read_paths:
                lines.append(f'  {{"tool":"read_file","args":{{"path":"{path}"}}}}')
            for path in required_write_paths:
                lines.append(
                    f'  {{"tool":"write_file","args":{{"path":"{path}","content":"<actual content>"}}}}'
                )
            if len(required_statuses) == 1:
                status = required_statuses[0]
                if status == "blocked":
                    lines.append(
                        '  {"tool":"update_issue_status","args":{"status":"blocked","wait_reason":"review"}}'
                    )
                else:
                    lines.append(f'  {{"tool":"update_issue_status","args":{{"status":"{status}"}}}}')
            elif required_statuses:
                lines.append(
                    "  "
                    + '{"tool":"update_issue_status","args":{"status":"<one of '
                    + "|".join(required_statuses)
                    + '>"}}'
                )

        return "\n".join(lines)

    def _deterministic_failure_message(self, reason: str) -> str:
        reason_key = str(reason or "").strip().lower()
        mapping = {
            "progress_contract_not_met": "Deterministic failure: progress contract not met after corrective reprompt.",
            "guard_rejection_payload_contract_not_met": "Deterministic failure: guard rejection payload contract not met after corrective reprompt.",
            "read_path_contract_not_met": "Deterministic failure: read path contract not met after corrective reprompt.",
            "write_path_contract_not_met": "Deterministic failure: write path contract not met after corrective reprompt.",
            "architecture_decision_contract_not_met": "Deterministic failure: architecture decision contract not met after corrective reprompt.",
        }
        return mapping.get(
            reason_key,
            "Deterministic failure: turn contract not met after corrective reprompt.",
        )

    def _required_read_paths(self, context: Dict[str, Any]) -> List[str]:
        return [
            str(path).strip()
            for path in (context.get("required_read_paths") or [])
            if str(path).strip()
        ]

    def _required_write_paths(self, context: Dict[str, Any]) -> List[str]:
        return [
            str(path).strip()
            for path in (context.get("required_write_paths") or [])
            if str(path).strip()
        ]

    def _observed_read_paths(self, turn: ExecutionTurn) -> List[str]:
        return [
            str(call.args.get("path", "")).strip()
            for call in turn.tool_calls
            if call.tool == "read_file"
        ]

    def _observed_write_paths(self, turn: ExecutionTurn) -> List[str]:
        return [
            str(call.args.get("path", "")).strip()
            for call in turn.tool_calls
            if call.tool == "write_file"
        ]

    def _progress_contract_diagnostics(
        self,
        turn: ExecutionTurn,
        role: RoleConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        observed_tools = [call.tool for call in (turn.tool_calls or []) if call.tool]
        required_action_tools = [str(t) for t in (context.get("required_action_tools") or []) if t]
        required_statuses = [str(s).strip().lower() for s in (context.get("required_statuses") or []) if s]
        missing_required = [tool for tool in required_action_tools if tool not in observed_tools]
        observed_statuses = [
            str(call.args.get("status", "")).strip().lower()
            for call in (turn.tool_calls or [])
            if call.tool == "update_issue_status"
        ]
        return {
            "ok": self._meets_progress_contract(turn, role, context),
            "required_action_tools": required_action_tools,
            "required_statuses": required_statuses,
            "observed_tools": observed_tools,
            "missing_required_tools": missing_required,
            "observed_statuses": observed_statuses,
        }

    def _meets_progress_contract(self, turn: ExecutionTurn, role: RoleConfig, context: Dict[str, Any]) -> bool:
        allowed = set(role.tools or [])
        called_tools = {call.tool for call in (turn.tool_calls or []) if call.tool}
        required_tools = {
            str(tool)
            for tool in (context.get("required_action_tools") or [])
            if tool
        }
        required_statuses = {
            str(status).strip().lower()
            for status in (context.get("required_statuses") or [])
            if status
        }
        observational_tools = {
            "get_issue_context",
            "read_file",
            "list_directory",
            "list_dir",
        }
        blocked_wait_reasons = {"resource", "dependency", "review", "input", "system"}

        if allowed:
            if not turn.tool_calls:
                return False
            if not any(call.tool in allowed for call in turn.tool_calls):
                return False
        elif turn.tool_calls:
            pass
        elif not (turn.content or "").strip():
            return False

        # Hard minimum progress: avoid turns that only fetch context and never act.
        if called_tools and called_tools.issubset(observational_tools):
            return False

        # Optional seat-level contract (if supplied by orchestrator policy).
        if required_tools and not required_tools.issubset(called_tools):
            return False

        if required_statuses:
            status_match = False
            for call in turn.tool_calls:
                if call.tool != "update_issue_status":
                    continue
                status = str(call.args.get("status", "")).strip().lower()
                if status not in required_statuses:
                    continue
                if status == "blocked":
                    wait_reason = str(call.args.get("wait_reason", "")).strip().lower()
                    if wait_reason not in blocked_wait_reasons:
                        continue
                status_match = True
                break
            if not status_match:
                return False

        return True

    def _meets_write_path_contract(self, turn: ExecutionTurn, context: Dict[str, Any]) -> bool:
        required_paths = self._required_write_paths(context)
        if not required_paths:
            return True

        observed_paths = self._observed_write_paths(turn)
        if not observed_paths:
            return False
        observed_set = {p for p in observed_paths if p}
        return set(required_paths).issubset(observed_set)

    def _meets_guard_rejection_payload_contract(self, turn: ExecutionTurn, context: Dict[str, Any]) -> bool:
        stage_gate_mode = str(context.get("stage_gate_mode", "")).strip().lower()
        if stage_gate_mode != "review_required":
            return True

        blocked_status = False
        blocked_wait_reason = ""
        for call in turn.tool_calls:
            if call.tool != "update_issue_status":
                continue
            status = str(call.args.get("status", "")).strip().lower()
            if status == "blocked":
                blocked_status = True
                blocked_wait_reason = str(call.args.get("wait_reason", "")).strip().lower()
                break

        if not blocked_status:
            return True

        payload = self._extract_guard_review_payload(turn.content or "")
        rationale = str(payload.get("rationale", "") or "").strip()
        violations = [
            str(item).strip()
            for item in (payload.get("violations", []) or [])
            if str(item).strip()
        ]
        actions = [
            str(item).strip()
            for item in (payload.get("remediation_actions", []) or [])
            if str(item).strip()
        ]
        if blocked_wait_reason == "dependency":
            dep_context = context.get("dependency_context") or {}
            if "depends_on" in dep_context:
                unresolved = dep_context.get("unresolved_dependencies") or []
                if not unresolved:
                    return False
        return bool(rationale and violations and actions)

    def _meets_read_path_contract(self, turn: ExecutionTurn, context: Dict[str, Any]) -> bool:
        required_paths = self._required_read_paths(context)
        if not required_paths:
            return True

        observed_paths = self._observed_read_paths(turn)
        if not observed_paths:
            return False
        observed_set = {p for p in observed_paths if p}
        return set(required_paths).issubset(observed_set)

    def _meets_architecture_decision_contract(self, turn: ExecutionTurn, context: Dict[str, Any]) -> bool:
        if not bool(context.get("architecture_decision_required")):
            return True

        required_path = str(context.get("architecture_decision_path", "agent_output/design.txt")).strip()
        if not required_path:
            return False

        allowed_patterns = {
            str(v).strip().lower()
            for v in (context.get("architecture_allowed_patterns") or ["monolith", "microservices"])
            if str(v).strip()
        }
        if not allowed_patterns:
            allowed_patterns = {"monolith", "microservices"}

        forced_pattern = str(context.get("architecture_forced_pattern", "") or "").strip().lower()
        forced_frontend_framework = str(context.get("frontend_framework_forced", "") or "").strip().lower()
        allowed_frontend_frameworks = {
            str(v).strip().lower()
            for v in (context.get("frontend_framework_allowed") or ["vue", "react", "angular"])
            if str(v).strip()
        }
        required_evidence_keys = {
            "estimated_domains",
            "external_integrations",
            "independent_scaling_needs",
            "deployment_complexity",
            "team_parallelism",
            "operational_maturity",
        }

        for call in turn.tool_calls:
            if call.tool != "write_file":
                continue
            path = str(call.args.get("path", "")).strip()
            if path != required_path:
                continue

            raw_content = call.args.get("content", "")
            if not isinstance(raw_content, str):
                return False
            try:
                payload = json.loads(raw_content)
            except json.JSONDecodeError:
                return False
            if not isinstance(payload, dict):
                return False

            recommendation = str(payload.get("recommendation", "")).strip().lower()
            if recommendation not in allowed_patterns:
                return False
            if forced_pattern and recommendation != forced_pattern:
                return False

            frontend_framework = str(payload.get("frontend_framework", "")).strip().lower()
            if frontend_framework:
                if frontend_framework not in allowed_frontend_frameworks:
                    return False
            if forced_frontend_framework and frontend_framework != forced_frontend_framework:
                return False

            confidence = payload.get("confidence")
            try:
                confidence_value = float(confidence)
            except (TypeError, ValueError):
                return False
            if confidence_value < 0.0 or confidence_value > 1.0:
                return False

            evidence = payload.get("evidence")
            if not isinstance(evidence, dict):
                return False
            if not required_evidence_keys.issubset(set(evidence.keys())):
                return False
            return True

        return False

    def _extract_guard_review_payload(self, content: str) -> Dict[str, Any]:
        blob = content or ""
        decoder = json.JSONDecoder()
        candidates: List[Dict[str, Any]] = []

        import re
        fenced_matches = re.findall(r"```json\s*([\s\S]*?)```", blob, flags=re.IGNORECASE)
        for chunk in fenced_matches:
            try:
                parsed = json.loads(chunk.strip())
                if isinstance(parsed, dict):
                    candidates.append(parsed)
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

        start = 0
        while True:
            brace_index = blob.find("{", start)
            if brace_index == -1:
                break
            try:
                parsed, end_pos = decoder.raw_decode(blob[brace_index:])
                if isinstance(parsed, dict):
                    candidates.append(parsed)
                start = brace_index + max(end_pos, 1)
            except json.JSONDecodeError:
                start = brace_index + 1

        for parsed in candidates:
            if {"rationale", "violations", "remediation_actions"} & set(parsed.keys()):
                return parsed
        return {}

    def _message_hash(self, messages: List[Dict[str, str]]) -> str:
        normalized = json.dumps(messages, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def _write_turn_artifact(
        self,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        filename: str,
        content: str,
    ) -> None:
        out_dir = (
            self.workspace
            / "observability"
            / sanitize_name(session_id)
            / sanitize_name(issue_id)
            / f"{turn_index:03d}_{sanitize_name(role_name)}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / filename).write_text(content, encoding="utf-8")

    def _state_delta_from_tool_calls(self, context: Dict[str, Any], turn: ExecutionTurn) -> Dict[str, Any]:
        current = context.get("current_status")
        requested = None
        for call in turn.tool_calls:
            if call.tool == "update_issue_status":
                requested = call.args.get("status")
                break
        return {"from": current, "to": requested}

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
        payload = {
            "run_id": session_id,
            "issue_id": issue_id,
            "turn_index": turn_index,
            "role": role_name,
            "prompt_hash": prompt_hash,
            "model": selected_model,
            "tool_calls": tool_calls,
            "state_delta": state_delta,
            "prompt_metadata": prompt_metadata or {},
            "captured_at": datetime.now(UTC).isoformat(),
        }
        self._write_turn_artifact(
            session_id,
            issue_id,
            role_name,
            turn_index,
            "checkpoint.json",
            json.dumps(payload, indent=2, ensure_ascii=False),
        )

    def _tool_replay_key(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        normalized = json.dumps({"tool": tool_name, "args": tool_args}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]

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
        replay_key = self._tool_replay_key(tool_name, tool_args)
        out_dir = (
            self.workspace
            / "observability"
            / sanitize_name(session_id)
            / sanitize_name(issue_id)
            / f"{turn_index:03d}_{sanitize_name(role_name)}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"tool_result_{sanitize_name(tool_name)}_{replay_key}.json"

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
        if not resume_mode:
            return None
        path = self._tool_result_path(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            tool_name=tool_name,
            tool_args=tool_args,
        )
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return None

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
        path = self._tool_result_path(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            tool_name=tool_name,
            tool_args=tool_args,
        )
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


class ToolValidationError(Exception):
    """Tool call validation failed."""

    def __init__(self, violations: List[str]):
        self.violations = violations
        super().__init__(f"Tool validation failed: {violations}")


class ModelTimeoutError(Exception):
    """Model request timed out."""
    pass
