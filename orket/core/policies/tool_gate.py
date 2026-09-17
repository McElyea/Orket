"""
Pure tool gate policy over explicit request, configuration and file facts.

Intercepts tool calls before execution to enforce organizational invariants.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Protocol

from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.schema import CardStatus, CardType, OrganizationConfig


class ToolGateViolation(Exception):
    """Raised when a tool call violates organizational policy."""


@dataclass(frozen=True)
class FileWriteFacts:
    requested_path: str
    relative_path: str
    error: str | None = None


class ToolGateValidator(Protocol):
    async def validate(
        self, tool_name: str, args: dict[str, Any], context: dict[str, Any], roles: list[str]
    ) -> str | None: ...


class ToolGate:
    """Validates tool calls against organizational policy before execution."""

    def __init__(self, organization: OrganizationConfig | None):
        self.org = deepcopy(organization)

    def validate(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict[str, Any],
        roles: list[str],
        *,
        file_facts: FileWriteFacts | None = None,
    ) -> str | None:
        if tool_name == "write_file":
            violation = self._validate_file_write(args, context, roles, file_facts)
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
        args: dict[str, Any],
        context: dict[str, Any],
        roles: list[str],
        facts: FileWriteFacts | None,
    ) -> str | None:
        file_path = args.get("path")
        if not file_path:
            return "write_file requires 'path' argument"
        if facts is None:
            return "write_file requires application file-validation facts"
        if facts.error:
            return facts.error
        if not facts.requested_path or not facts.relative_path:
            return "write_file requires resolved application path facts"
        if (
            self.org
            and hasattr(self.org, "forbidden_file_types")
            and any(facts.requested_path.endswith(ext) for ext in self.org.forbidden_file_types)
        ):
            return f"Policy violation: File type not allowed ({file_path})"
        violation = self._validate_dependency_file_ownership(
            relative_path=facts.relative_path,
            context=context,
            roles=roles,
        )
        return violation or self._validate_deployment_file_ownership(
            relative_path=facts.relative_path,
            context=context,
            roles=roles,
        )

    def _validate_dependency_file_ownership(
        self,
        *,
        relative_path: str,
        context: dict[str, Any],
        roles: list[str],
    ) -> str | None:
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

        rel_path = relative_path
        managed_set = {str(path).strip().replace("\\", "/") for path in managed_files if str(path).strip()}
        if rel_path not in managed_set:
            return None

        normalized_roles = {str(role).strip().lower() for role in roles if str(role).strip()}
        seat = str(context.get("role", "")).strip().lower()
        if seat:
            normalized_roles.add(seat)

        if normalized_roles & allowed_role_set:
            return None
        return f"Policy violation: dependency manifest '{rel_path}' is owned by roles {sorted(allowed_role_set)}"

    def _validate_deployment_file_ownership(
        self,
        *,
        relative_path: str,
        context: dict[str, Any],
        roles: list[str],
    ) -> str | None:
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

        rel_path = relative_path
        managed_set = {str(path).strip().replace("\\", "/") for path in managed_files if str(path).strip()}
        if rel_path not in managed_set:
            return None

        normalized_roles = {str(role).strip().lower() for role in roles if str(role).strip()}
        seat = str(context.get("role", "")).strip().lower()
        if seat:
            normalized_roles.add(seat)

        if normalized_roles & allowed_role_set:
            return None
        return f"Policy violation: deployment artifact '{rel_path}' is owned by roles {sorted(allowed_role_set)}"

    def _validate_state_change(
        self,
        args: dict[str, Any],
        context: dict[str, Any],
        roles: list[str],
    ) -> str | None:
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

        try:
            current_status = CardStatus(current_status_str)
            card_type = self._resolve_card_type(context)
            wait_reason = args.get("wait_reason")
            StateMachine.validate_transition(
                card_type,
                current_status,
                requested_status,
                roles=roles,
                wait_reason=wait_reason,
            )
        except (StateMachineError, ValueError, TypeError) as e:
            return str(e)

        return None

    def _resolve_card_type(self, context: dict[str, Any]) -> CardType:
        raw_card_type = context.get("card_type", CardType.ISSUE.value)
        if isinstance(raw_card_type, CardType):
            return raw_card_type
        return CardType(str(raw_card_type).strip().lower())

    def _validate_destructive_operation(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict[str, Any],
    ) -> str | None:
        if not args.get("confirm", False):
            return f"Destructive operation '{tool_name}' requires explicit confirmation (confirm=true)"
        return None

    def _validate_issue_creation(
        self,
        args: dict[str, Any],
        context: dict[str, Any],
    ) -> str | None:
        summary = args.get("summary", "")
        if len(summary) < 5:
            return "Issue summary must be at least 5 characters"
        return None
