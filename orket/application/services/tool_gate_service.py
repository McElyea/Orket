"""Gather file facts in an owned worker before applying pure tool policy."""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.policies.tool_gate import FileWriteFacts
from orket.core.policies.tool_gate import ToolGate as ToolGatePolicy
from orket.schema import OrganizationConfig
from orket.services.ast_validator import ASTValidator
from orket.services.idesign_validator import iDesignValidator

logger = logging.getLogger(__name__)


class ToolGate:
    """Application implementation of the async ToolGateValidator contract."""

    def __init__(self, organization: OrganizationConfig | None, workspace_root: Path):
        self._policy = ToolGatePolicy(organization)
        self.org = self._policy.org
        self.workspace_root = Path(workspace_root)
        self.idesign_validator = iDesignValidator(self.org)

    async def validate(
        self, tool_name: str, args: dict[str, Any], context: dict[str, Any], roles: list[str]
    ) -> str | None:
        context = context or {}
        captured_args, captured_roles = deepcopy(args), list(roles)
        captured_context = {
            key: context.get(key)
            for key in (
                "role",
                "current_role",
                "issue_id",
                "card_id",
                "idesign_enabled",
                "current_status",
                "card_type",
            )
            if key in context
        }
        facts = None
        if tool_name == "write_file" and captured_args.get("path"):
            facts = await run_owned_thread(
                partial(self._file_write_facts, captured_args, captured_context),
                label="tool-gate-file-validation",
            )
        if tool_name == "update_issue_status" and self.org and getattr(self.org, "bypass_governance", False):
            logger.warning("Ignoring bypass_governance during tool gate transition validation.")
        return self._policy.validate(tool_name, captured_args, captured_context, captured_roles, file_facts=facts)

    def _file_write_facts(self, args: dict[str, Any], context: dict[str, Any]) -> FileWriteFacts:
        """Invoked only by the owned worker; resolution and AST work stay off the event loop."""
        file_path = args["path"]
        try:
            full_path = Path(file_path)
            if not full_path.is_absolute():
                full_path = self.workspace_root / full_path
            root, resolved = self.workspace_root.resolve(), full_path.resolve()
            if not resolved.is_relative_to(root):
                return FileWriteFacts("", "", f"Security violation: Cannot write outside workspace ({file_path})")
            if bool(context.get("idesign_enabled", False)):
                # This transient validation view has no temporal semantics and is never published.
                turn = ExecutionTurn(
                    role=str(context.get("role") or context.get("current_role") or "unknown"),
                    issue_id=str(context.get("issue_id") or context.get("card_id") or "unknown"),
                    tool_calls=[ToolCall(tool="write_file", args=args)],
                    timestamp=datetime.min.replace(tzinfo=UTC),
                )
                violations = self.idesign_validator.validate_turn(turn, self.workspace_root)
                if violations:
                    violation = violations[0]
                    return FileWriteFacts(
                        "", "", f"iDesign Violation: {violation.message} (Code: {violation.code.value})"
                    )
                if full_path.suffix == ".py":
                    errors = [
                        v
                        for v in ASTValidator.validate_code(args.get("content", ""), full_path.name)
                        if v.severity == "error"
                    ]
                    if errors:
                        return FileWriteFacts(
                            "", "", f"iDesign AST Violation: {errors[0].message} (Line: {errors[0].line})"
                        )
            return FileWriteFacts(str(full_path), resolved.relative_to(root).as_posix())
        except (OSError, ValueError, TypeError) as exc:
            return FileWriteFacts("", "", f"Invalid file path: {exc}")
