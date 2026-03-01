from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.domain.execution import ExecutionTurn
from orket.schema import RoleConfig

from .turn_contract_rules import (
    consistency_scope_diagnostics,
    hallucination_scope_diagnostics,
    meets_architecture_decision_contract,
    observed_read_paths,
    observed_write_paths,
    parse_architecture_decision_payload,
    required_read_paths,
    required_write_paths,
    security_scope_diagnostics,
)
from .turn_response_parser import ResponseParser


class ContractValidator:
    """Evaluate turn contract compliance and produce deterministic diagnostics."""

    def __init__(self, workspace: Path, response_parser: ResponseParser) -> None:
        self.workspace = workspace
        self.response_parser = response_parser

    def collect_contract_violations(
        self,
        turn: ExecutionTurn,
        role: RoleConfig,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        violations: list[dict[str, Any]] = []
        self._append_progress_violations(violations, turn, role, context)
        self._append_contract_violations(violations, turn, context)
        self._append_scope_violations(violations, turn, context)
        return violations

    def _append_progress_violations(
        self,
        violations: list[dict[str, Any]],
        turn: ExecutionTurn,
        role: RoleConfig,
        context: dict[str, Any],
    ) -> None:
        progress_diag = self.progress_contract_diagnostics(turn, role, context)
        if progress_diag.get("ok", False):
            return
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

    def _append_contract_violations(
        self,
        violations: list[dict[str, Any]],
        turn: ExecutionTurn,
        context: dict[str, Any],
    ) -> None:
        if not self.meets_write_path_contract(turn, context):
            violations.append(
                {
                    "reason": "write_path_contract_not_met",
                    "required_write_paths": self.required_write_paths(context),
                    "observed_write_paths": self.observed_write_paths(turn),
                }
            )
        if not self.meets_read_path_contract(turn, context):
            violations.append(
                {
                    "reason": "read_path_contract_not_met",
                    "required_read_paths": self.required_read_paths(context),
                    "observed_read_paths": self.observed_read_paths(turn),
                }
            )
        if not self.meets_architecture_decision_contract(turn, context):
            violations.append(
                {
                    "reason": "architecture_decision_contract_not_met",
                    "architecture_mode": context.get("architecture_mode"),
                    "architecture_decision_path": context.get("architecture_decision_path"),
                }
            )
        if not self.meets_guard_rejection_payload_contract(turn, context):
            violations.append(
                {
                    "reason": "guard_rejection_payload_contract_not_met",
                    "stage_gate_mode": context.get("stage_gate_mode"),
                }
            )

    def _append_scope_violations(
        self,
        violations: list[dict[str, Any]],
        turn: ExecutionTurn,
        context: dict[str, Any],
    ) -> None:
        scope_checks = [
            ("hallucination_scope_contract_not_met", self.hallucination_scope_diagnostics(turn, context)),
            ("security_scope_contract_not_met", self.security_scope_diagnostics(turn, context)),
            ("consistency_scope_contract_not_met", self.consistency_scope_diagnostics(turn, context)),
        ]
        for reason, diagnostics in scope_checks:
            if not diagnostics.get("violations"):
                continue
            violations.append(
                {
                    "reason": reason,
                    "scope": diagnostics.get("scope", {}),
                    "violations": diagnostics.get("violations", []),
                }
            )

    def progress_contract_diagnostics(
        self,
        turn: ExecutionTurn,
        role: RoleConfig,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        observed_tools = [call.tool for call in (turn.tool_calls or []) if call.tool]
        allowed_tools = {str(tool).strip() for tool in (role.tools or []) if str(tool).strip()}
        required_action_tools = [str(t) for t in (context.get("required_action_tools") or []) if t]
        if allowed_tools:
            required_action_tools = [tool for tool in required_action_tools if tool in allowed_tools]
        if "read_file" in required_action_tools and not self.required_read_paths(context):
            required_action_tools = [tool for tool in required_action_tools if tool != "read_file"]
        required_statuses = [str(s).strip().lower() for s in (context.get("required_statuses") or []) if s]
        missing_required = [tool for tool in required_action_tools if tool not in observed_tools]
        observed_statuses = [
            str(call.args.get("status", "")).strip().lower()
            for call in (turn.tool_calls or [])
            if call.tool == "update_issue_status"
        ]
        return {
            "ok": self.meets_progress_contract(turn, role, context),
            "required_action_tools": required_action_tools,
            "required_statuses": required_statuses,
            "observed_tools": observed_tools,
            "missing_required_tools": missing_required,
            "observed_statuses": observed_statuses,
        }

    def meets_progress_contract(self, turn: ExecutionTurn, role: RoleConfig, context: dict[str, Any]) -> bool:
        allowed = set(role.tools or [])
        called_tools = {call.tool for call in (turn.tool_calls or []) if call.tool}
        required_tools = {str(tool) for tool in (context.get("required_action_tools") or []) if tool}
        if allowed:
            required_tools = {tool for tool in required_tools if tool in allowed}
        required_statuses = {str(status).strip().lower() for status in (context.get("required_statuses") or []) if status}
        observational_tools = {"get_issue_context", "read_file", "list_directory", "list_dir"}
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

        if called_tools and called_tools.issubset(observational_tools):
            return False

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

    def meets_write_path_contract(self, turn: ExecutionTurn, context: dict[str, Any]) -> bool:
        required_paths = self.required_write_paths(context)
        if not required_paths:
            return True

        observed_paths = self.observed_write_paths(turn)
        if not observed_paths:
            return False
        observed_set = {p for p in observed_paths if p}
        return set(required_paths).issubset(observed_set)

    def meets_guard_rejection_payload_contract(self, turn: ExecutionTurn, context: dict[str, Any]) -> bool:
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

        payload = self.extract_guard_review_payload(turn.content or "")
        rationale = str(payload.get("rationale", "") or "").strip()
        violations = [str(item).strip() for item in (payload.get("violations", []) or []) if str(item).strip()]
        actions = [str(item).strip() for item in (payload.get("remediation_actions", []) or []) if str(item).strip()]
        if blocked_wait_reason == "dependency":
            dep_context = context.get("dependency_context") or {}
            if "depends_on" in dep_context:
                unresolved = dep_context.get("unresolved_dependencies") or []
                if not unresolved:
                    return False
        return bool(rationale and violations and actions)

    def meets_read_path_contract(self, turn: ExecutionTurn, context: dict[str, Any]) -> bool:
        required_paths = self.required_read_paths(context)
        if not required_paths:
            return True

        observed_paths = self.observed_read_paths(turn)
        if not observed_paths:
            return False
        observed_set = {p for p in observed_paths if p}
        return set(required_paths).issubset(observed_set)

    def meets_architecture_decision_contract(self, turn: ExecutionTurn, context: dict[str, Any]) -> bool:
        return meets_architecture_decision_contract(turn, context)

    @staticmethod
    def parse_architecture_decision_payload(raw_content: str) -> dict[str, Any] | None:
        return parse_architecture_decision_payload(raw_content)

    def hallucination_scope_diagnostics(self, turn: ExecutionTurn, context: dict[str, Any]) -> dict[str, Any]:
        return hallucination_scope_diagnostics(turn, context, self.non_json_residue)

    @staticmethod
    def security_scope_diagnostics(turn: ExecutionTurn, context: dict[str, Any]) -> dict[str, Any]:
        return security_scope_diagnostics(turn, context)

    def consistency_scope_diagnostics(self, turn: ExecutionTurn, context: dict[str, Any]) -> dict[str, Any]:
        return consistency_scope_diagnostics(turn, context, self.non_json_residue)

    def required_read_paths(self, context: dict[str, Any]) -> list[str]:
        return required_read_paths(context, self.workspace)

    @staticmethod
    def required_write_paths(context: dict[str, Any]) -> list[str]:
        return required_write_paths(context)

    @staticmethod
    def observed_read_paths(turn: ExecutionTurn) -> list[str]:
        return observed_read_paths(turn)

    @staticmethod
    def observed_write_paths(turn: ExecutionTurn) -> list[str]:
        return observed_write_paths(turn)

    def non_json_residue(self, content: str) -> str:
        return self.response_parser.non_json_residue(content)

    def extract_guard_review_payload(self, content: str) -> dict[str, Any]:
        return self.response_parser.extract_guard_review_payload(content)
