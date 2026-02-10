"""
Governance Auditor - The Reconstruction

Single Responsibility: Validate that an execution turn followed the rules.

Checks:
- Tool calls were permitted for the role
- State transitions were valid
- No security policy violations
- Budget/credit limits respected
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path

from orket.domain.execution import ExecutionTurn, ToolCall
from orket.logging import log_event


@dataclass
class AuditResult:
    """Result of auditing an execution turn."""
    passed: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def clean(cls) -> AuditResult:
        return cls(passed=True)

    @classmethod
    def failed(cls, violations: List[str]) -> AuditResult:
        return cls(passed=False, violations=violations)


class GovernanceAuditor:
    """
    Validates execution turns against governance rules.

    Extracted from the _traction_loop god method to enforce SRP.
    This is the mechanical enforcement layer - no discretion, no mercy.
    """

    
    # Default limit: 1MB to prevent memory exhaustion and token limit issues
    DEFAULT_MAX_FILE_SIZE = 1_000_000 

    def __init__(
        self,
        workspace: Path,
        role_tool_permissions: Optional[Dict[str, List[str]]] = None,
        max_tool_calls_per_turn: int = 10,
        max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE,
    ):
        self.workspace = workspace
        self.role_permissions = role_tool_permissions or {}
        self.max_tool_calls = max_tool_calls_per_turn
        self.max_file_size = max_file_size_bytes

    def audit(self, turn: ExecutionTurn, role_name: str) -> AuditResult:
        """
        Audit a completed execution turn.

        Args:
            turn: The execution turn to audit
            role_name: The role that executed the turn

        Returns:
            AuditResult with pass/fail and any violations
        """
        violations = []
        warnings = []

        # 1. Check tool call count
        if len(turn.tool_calls) > self.max_tool_calls:
            violations.append(
                f"Too many tool calls: {len(turn.tool_calls)} (max {self.max_tool_calls})"
            )

        # 2. Check each tool call
        for tc in turn.tool_calls:
            tool_violations = self._audit_tool_call(tc, role_name)
            violations.extend(tool_violations)

        # 3. Check for empty turns (no content, no tools)
        if not turn.content and not turn.tool_calls:
            warnings.append("Empty turn: No content or tool calls produced")

        # 4. Check for error-only turns
        error_calls = [tc for tc in turn.tool_calls if tc.error]
        if error_calls and len(error_calls) == len(turn.tool_calls):
            violations.append(
                f"All {len(error_calls)} tool calls failed"
            )

        # Log audit result
        result = AuditResult(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings
        )

        log_event(
            "governance_audit",
            {
                "role": role_name,
                "issue_id": turn.issue_id,
                "passed": result.passed,
                "violations": result.violations,
                "warnings": result.warnings,
                "tool_calls_audited": len(turn.tool_calls)
            },
            self.workspace
        )

        return result

    def _audit_tool_call(self, tool_call: ToolCall, role_name: str) -> List[str]:
        """Audit a single tool call against governance rules."""
        violations = []

        # Check role permissions
        if self.role_permissions:
            allowed_tools = self.role_permissions.get(role_name, [])
            if allowed_tools and tool_call.tool not in allowed_tools:
                violations.append(
                    f"Role '{role_name}' not permitted to use tool '{tool_call.tool}'"
                )

        # Check write_file specifics
        if tool_call.tool == "write_file":
            violations.extend(self._audit_write_file(tool_call, role_name))

        # Check update_issue_status specifics
        if tool_call.tool == "update_issue_status":
            violations.extend(self._audit_status_change(tool_call, role_name))

        return violations

    def _audit_write_file(self, tool_call: ToolCall, role_name: str) -> List[str]:
        """Audit write_file tool calls for security violations."""
        violations = []
        args = tool_call.args or {}

        # Check file size
        content = args.get("content", "")
        if isinstance(content, str) and len(content.encode("utf-8")) > self.max_file_size:
            violations.append(
                f"File content exceeds max size: {len(content.encode('utf-8'))} bytes"
            )

        # Check for suspicious paths
        path = args.get("path", "")
        suspicious_patterns = [".env", "credentials", "secret", "password", ".ssh", ".git"]
        for pattern in suspicious_patterns:
            if pattern in path.lower():
                violations.append(
                    f"Suspicious file path detected: '{path}' (contains '{pattern}')"
                )

        return violations

    def _audit_status_change(self, tool_call: ToolCall, role_name: str) -> List[str]:
        """Audit status change tool calls for permission violations."""
        violations = []
        args = tool_call.args or {}
        new_status = args.get("status", "").lower()

        # Only project_manager can cancel
        if new_status == "canceled" and "project_manager" not in role_name.lower():
            violations.append(
                f"Role '{role_name}' cannot set status to 'canceled' (PM only)"
            )

        # Only reviewer roles can set to done
        reviewer_roles = ["integrity_guard", "reviewer", "lead_architect"]
        if new_status == "done" and not any(r in role_name.lower() for r in reviewer_roles):
            violations.append(
                f"Role '{role_name}' cannot set status to 'done' (reviewer roles only)"
            )

        return violations
