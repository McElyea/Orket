"""
Tool Gate Service - Phase 2: Mechanical Enforcement

Intercepts tool calls BEFORE execution to enforce organizational invariants.
This is the centralized policy enforcement point for all agent tool usage.
"""
from typing import Dict, Any, Optional, List
from pathlib import Path
from orket.schema import OrganizationConfig, CardStatus, CardType
from orket.domain.state_machine import StateMachine


class ToolGateViolation(Exception):
    """Raised when a tool call violates organizational policy."""
    pass


class ToolGate:
    """
    Validates tool calls against organizational policy before execution.
    Enforces mechanical governance at the tool level.
    """

    def __init__(self, organization: Optional[OrganizationConfig], workspace_root: Path):
        self.org = organization
        self.workspace_root = workspace_root

    def validate(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Dict[str, Any],
        roles: List[str]
    ) -> Optional[str]:
        """
        Validates a tool call before execution.

        Args:
            tool_name: Name of the tool being called
            args: Tool arguments
            context: Execution context (session_id, issue_id, etc.)
            roles: Active roles for this turn

        Returns:
            None if allowed, error message string if blocked
        """

        # 1. File Write Boundary Enforcement
        if tool_name == "write_file":
            violation = self._validate_file_write(args)
            if violation:
                return violation

        # 2. State Transition Enforcement (consolidated from ExecutionPipeline)
        if tool_name == "update_issue_status":
            violation = self._validate_state_change(args, context, roles)
            if violation:
                return violation

        # 3. Destructive Operation Protection
        if tool_name in ["delete_file", "reset_issue"]:
            violation = self._validate_destructive_operation(tool_name, args, context)
            if violation:
                return violation

        # 4. Issue Creation Restrictions (prevent Epic bloat)
        if tool_name == "create_issue":
            violation = self._validate_issue_creation(args, context)
            if violation:
                return violation

        return None  # Tool call is allowed

    def _validate_file_write(self, args: Dict[str, Any]) -> Optional[str]:
        """Enforce workspace boundaries and file type restrictions."""
        file_path = args.get("path")
        if not file_path:
            return "write_file requires 'path' argument"

        # Normalize path
        try:
            full_path = Path(file_path)
            if not full_path.is_absolute():
                full_path = self.workspace_root / file_path

            # Check if path escapes workspace
            try:
                full_path.resolve().relative_to(self.workspace_root.resolve())
            except ValueError:
                return f"Security violation: Cannot write outside workspace ({file_path})"

            # Check for suspicious file types (if configured)
            if self.org and hasattr(self.org, "forbidden_file_types"):
                forbidden = self.org.forbidden_file_types
                if any(str(full_path).endswith(ext) for ext in forbidden):
                    return f"Policy violation: File type not allowed ({file_path})"

        except Exception as e:
            return f"Invalid file path: {e}"

        return None

    def _validate_state_change(
        self,
        args: Dict[str, Any],
        context: Dict[str, Any],
        roles: List[str]
    ) -> Optional[str]:
        """
        Enforce state machine rules for status transitions.
        Consolidated from ExecutionPipeline governance checks.
        """
        new_status_str = args.get("status")
        if not new_status_str:
            return "update_issue_status requires 'status' argument"

        try:
            requested_status = CardStatus(new_status_str)
        except ValueError:
            return f"Invalid status: {new_status_str}"

        # Get current status from context (set by ExecutionPipeline)
        current_status_str = context.get("current_status")
        if not current_status_str:
            return "Cannot validate transition: current status unknown"

        current_status = CardStatus(current_status_str)

        # Apply StateMachine validation
        if self.org and not getattr(self.org, "bypass_governance", False):
            try:
                wait_reason = args.get("wait_reason")
                StateMachine.validate_transition(
                    CardType.ISSUE,
                    current_status,
                    requested_status,
                    roles=roles,
                    wait_reason=wait_reason
                )
            except Exception as e:
                return str(e)

        return None

    def _validate_destructive_operation(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Protect against accidental destructive operations.
        Require explicit confirmation flag.
        """
        if not args.get("confirm", False):
            return f"Destructive operation '{tool_name}' requires explicit confirmation (confirm=true)"

        return None

    def _validate_issue_creation(
        self,
        args: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Prevent unbounded issue creation that could violate iDesign thresholds.
        """
        # This is a placeholder for future epic bloat prevention
        # Could check if adding this issue would exceed iDesign threshold
        # without proper decomposition

        summary = args.get("summary", "")
        if len(summary) < 5:
            return "Issue summary must be at least 5 characters"

        return None
