"""
Tool Gate Service - Mechanical Enforcement.

Intercepts tool calls before execution to enforce organizational invariants.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path

from orket.schema import OrganizationConfig, CardStatus, CardType
from orket.core.domain.state_machine import StateMachine, StateMachineError


class ToolGateViolation(Exception):
    """Raised when a tool call violates organizational policy."""


class ToolGate:
    """Validates tool calls against organizational policy before execution."""

    def __init__(self, organization: Optional[OrganizationConfig], workspace_root: Path):
        self.org = organization
        self.workspace_root = workspace_root

    def validate(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Dict[str, Any],
        roles: List[str],
    ) -> Optional[str]:
        if tool_name == "write_file":
            violation = self._validate_file_write(args)
            if violation:
                return violation

        if tool_name == "update_issue_status":
            violation = self._validate_state_change(args, context, roles)
            if violation:
                return violation

        if tool_name in ["delete_file", "reset_issue"]:
            violation = self._validate_destructive_operation(tool_name, args, context)
            if violation:
                return violation

        if tool_name == "create_issue":
            violation = self._validate_issue_creation(args, context)
            if violation:
                return violation

        return None

    def _validate_file_write(self, args: Dict[str, Any]) -> Optional[str]:
        file_path = args.get("path")
        if not file_path:
            return "write_file requires 'path' argument"

        try:
            full_path = Path(file_path)
            if not full_path.is_absolute():
                full_path = self.workspace_root / file_path

            try:
                full_path.resolve().relative_to(self.workspace_root.resolve())
            except ValueError:
                return f"Security violation: Cannot write outside workspace ({file_path})"

            from orket.services.idesign_validator import iDesignValidator
            from orket.services.ast_validator import ASTValidator
            from orket.domain.execution import ExecutionTurn, ToolCall

            temp_turn = ExecutionTurn(
                role="unknown",
                issue_id="unknown",
                tool_calls=[ToolCall(tool="write_file", args=args)],
            )

            violations = iDesignValidator.validate_turn(temp_turn, self.workspace_root)
            if violations:
                return f"iDesign Violation: {violations[0].message} (Code: {violations[0].code.value})"

            if full_path.suffix == ".py":
                content = args.get("content", "")
                ast_violations = ASTValidator.validate_code(content, full_path.name)
                errors = [v for v in ast_violations if v.severity == "error"]
                if errors:
                    return f"iDesign AST Violation: {errors[0].message} (Line: {errors[0].line})"

            if self.org and hasattr(self.org, "forbidden_file_types"):
                forbidden = self.org.forbidden_file_types
                if any(str(full_path).endswith(ext) for ext in forbidden):
                    return f"Policy violation: File type not allowed ({file_path})"

        except (OSError, ValueError, TypeError) as e:
            return f"Invalid file path: {e}"

        return None

    def _validate_state_change(
        self,
        args: Dict[str, Any],
        context: Dict[str, Any],
        roles: List[str],
    ) -> Optional[str]:
        new_status_str = args.get("status")
        if not new_status_str:
            return "update_issue_status requires 'status' argument"

        try:
            requested_status = CardStatus(new_status_str)
        except ValueError:
            return f"Invalid status: {new_status_str}"

        current_status_str = context.get("current_status")
        if not current_status_str:
            return "Cannot validate transition: current status unknown"

        current_status = CardStatus(current_status_str)

        if self.org and not getattr(self.org, "bypass_governance", False):
            try:
                wait_reason = args.get("wait_reason")
                StateMachine.validate_transition(
                    CardType.ISSUE,
                    current_status,
                    requested_status,
                    roles=roles,
                    wait_reason=wait_reason,
                )
            except (StateMachineError, ValueError, TypeError) as e:
                return str(e)

        return None

    def _validate_destructive_operation(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[str]:
        if not args.get("confirm", False):
            return f"Destructive operation '{tool_name}' requires explicit confirmation (confirm=true)"
        return None

    def _validate_issue_creation(
        self,
        args: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[str]:
        summary = args.get("summary", "")
        if len(summary) < 5:
            return "Issue summary must be at least 5 characters"
        return None

