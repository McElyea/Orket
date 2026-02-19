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
            violation = self._validate_file_write(args, context, roles)
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

    def _validate_file_write(
        self,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        roles: Optional[List[str]] = None,
    ) -> Optional[str]:
        context = context or {}
        roles = roles or []
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

            if self._idesign_enabled(context):
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

            ownership_violation = self._validate_dependency_file_ownership(
                full_path=full_path,
                context=context,
                roles=roles,
            )
            if ownership_violation:
                return ownership_violation

            deployment_ownership_violation = self._validate_deployment_file_ownership(
                full_path=full_path,
                context=context,
                roles=roles,
            )
            if deployment_ownership_violation:
                return deployment_ownership_violation

        except (OSError, ValueError, TypeError) as e:
            return f"Invalid file path: {e}"

        return None

    def _idesign_enabled(self, context: Dict[str, Any]) -> bool:
        if not isinstance(context, dict):
            return False
        return bool(context.get("idesign_enabled", False))

    def _validate_dependency_file_ownership(
        self,
        *,
        full_path: Path,
        context: Dict[str, Any],
        roles: List[str],
    ) -> Optional[str]:
        if not self.org or not isinstance(getattr(self.org, "process_rules", None), dict):
            return None
        process_rules = self.org.process_rules

        enabled = process_rules.get("dependency_file_ownership_enabled", False)
        if not enabled:
            return None

        managed_files = process_rules.get(
            "dependency_managed_files",
            [
                "agent_output/dependencies/pyproject.toml",
                "agent_output/dependencies/requirements.txt",
                "agent_output/dependencies/requirements-dev.txt",
                "agent_output/dependencies/package.json",
            ],
        )
        if not isinstance(managed_files, list):
            return None

        allowed_roles = process_rules.get("dependency_file_owner_roles", ["dependency_manager"])
        if not isinstance(allowed_roles, list):
            allowed_roles = ["dependency_manager"]
        allowed_role_set = {str(role).strip().lower() for role in allowed_roles if str(role).strip()}

        rel_path = str(full_path.resolve().relative_to(self.workspace_root.resolve())).replace("\\", "/")
        managed_set = {str(path).strip().replace("\\", "/") for path in managed_files if str(path).strip()}
        if rel_path not in managed_set:
            return None

        normalized_roles = {str(role).strip().lower() for role in roles if str(role).strip()}
        seat = str(context.get("role", "")).strip().lower()
        if seat:
            normalized_roles.add(seat)

        if normalized_roles & allowed_role_set:
            return None
        return (
            f"Policy violation: dependency manifest '{rel_path}' is owned by roles "
            f"{sorted(allowed_role_set)}"
        )

    def _validate_deployment_file_ownership(
        self,
        *,
        full_path: Path,
        context: Dict[str, Any],
        roles: List[str],
    ) -> Optional[str]:
        if not self.org or not isinstance(getattr(self.org, "process_rules", None), dict):
            return None
        process_rules = self.org.process_rules

        enabled = process_rules.get("deployment_file_ownership_enabled", False)
        if not enabled:
            return None

        managed_files = process_rules.get(
            "deployment_managed_files",
            [
                "agent_output/deployment/Dockerfile",
                "agent_output/deployment/docker-compose.yml",
                "agent_output/deployment/run_local.sh",
            ],
        )
        if not isinstance(managed_files, list):
            return None

        allowed_roles = process_rules.get("deployment_file_owner_roles", ["deployment_planner"])
        if not isinstance(allowed_roles, list):
            allowed_roles = ["deployment_planner"]
        allowed_role_set = {str(role).strip().lower() for role in allowed_roles if str(role).strip()}

        rel_path = str(full_path.resolve().relative_to(self.workspace_root.resolve())).replace("\\", "/")
        managed_set = {str(path).strip().replace("\\", "/") for path in managed_files if str(path).strip()}
        if rel_path not in managed_set:
            return None

        normalized_roles = {str(role).strip().lower() for role in roles if str(role).strip()}
        seat = str(context.get("role", "")).strip().lower()
        if seat:
            normalized_roles.add(seat)

        if normalized_roles & allowed_role_set:
            return None
        return (
            f"Policy violation: deployment artifact '{rel_path}' is owned by roles "
            f"{sorted(allowed_role_set)}"
        )

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
