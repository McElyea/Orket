from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from orket.application.services.tool_parser import ToolParser
from orket.core.domain.verification_scope import parse_verification_scope
from orket.domain.execution import ExecutionTurn
from orket.schema import RoleConfig

from .turn_path_resolver import PathResolver
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

        progress_diag = self.progress_contract_diagnostics(turn, role, context)
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

        hallucination_scope_diag = self.hallucination_scope_diagnostics(turn, context)
        if hallucination_scope_diag.get("violations"):
            violations.append(
                {
                    "reason": "hallucination_scope_contract_not_met",
                    "scope": hallucination_scope_diag.get("scope", {}),
                    "violations": hallucination_scope_diag.get("violations", []),
                }
            )
        security_scope_diag = self.security_scope_diagnostics(turn, context)
        if security_scope_diag.get("violations"):
            violations.append(
                {
                    "reason": "security_scope_contract_not_met",
                    "scope": security_scope_diag.get("scope", {}),
                    "violations": security_scope_diag.get("violations", []),
                }
            )
        consistency_scope_diag = self.consistency_scope_diagnostics(turn, context)
        if consistency_scope_diag.get("violations"):
            violations.append(
                {
                    "reason": "consistency_scope_contract_not_met",
                    "scope": consistency_scope_diag.get("scope", {}),
                    "violations": consistency_scope_diag.get("violations", []),
                }
            )

        return violations

    def progress_contract_diagnostics(
        self,
        turn: ExecutionTurn,
        role: RoleConfig,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        observed_tools = [call.tool for call in (turn.tool_calls or []) if call.tool]
        required_action_tools = [str(t) for t in (context.get("required_action_tools") or []) if t]
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
            payload = self.parse_architecture_decision_payload(raw_content)
            if payload is None or not isinstance(payload, dict):
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

    @staticmethod
    def parse_architecture_decision_payload(raw_content: str) -> dict[str, Any] | None:
        normalized = ToolParser.normalize_json_stringify(raw_content or "")
        try:
            payload = json.loads(normalized)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

        blob = str(raw_content or "")
        recommendation_match = re.search(
            r'"recommendation"\s*:\s*"?(monolith|microservices)"?',
            blob,
            flags=re.IGNORECASE,
        )
        confidence_match = re.search(r'"confidence"\s*:\s*([0-9]+(?:\.[0-9]+)?)', blob, flags=re.IGNORECASE)
        if not recommendation_match or not confidence_match:
            return None
        recommendation = recommendation_match.group(1).strip().lower()
        confidence = float(confidence_match.group(1))
        frontend_match = re.search(r'"frontend_framework"\s*:\s*"?(vue|react|angular)"?', blob, flags=re.IGNORECASE)
        frontend_framework = frontend_match.group(1).strip().lower() if frontend_match else ""

        evidence_keys = {
            "estimated_domains",
            "external_integrations",
            "independent_scaling_needs",
            "deployment_complexity",
            "team_parallelism",
            "operational_maturity",
        }
        if not all(f'"{key}"' in blob for key in evidence_keys):
            return None

        evidence = {key: True for key in evidence_keys}
        payload: dict[str, Any] = {
            "recommendation": recommendation,
            "confidence": confidence,
            "evidence": evidence,
        }
        if frontend_framework:
            payload["frontend_framework"] = frontend_framework
        return payload

    def hallucination_scope_diagnostics(self, turn: ExecutionTurn, context: dict[str, Any]) -> dict[str, Any]:
        scope = parse_verification_scope(context.get("verification_scope"))
        if not isinstance(scope, dict):
            return {"scope": {}, "violations": []}

        workspace_scope = {str(path).strip() for path in (scope.get("workspace") or []) if str(path).strip()}
        active_context_scope = {str(item).strip() for item in (scope.get("active_context") or []) if str(item).strip()}
        passive_context_scope = {
            str(item).strip() for item in (scope.get("passive_context") or []) if str(item).strip()
        }
        archived_context_scope = {
            str(item).strip() for item in (scope.get("archived_context") or []) if str(item).strip()
        }
        declared_interfaces_scope = {
            str(item).strip() for item in (scope.get("declared_interfaces") or []) if str(item).strip()
        }
        strict_grounding = bool(scope.get("strict_grounding", False))
        max_workspace_items = scope.get("max_workspace_items")
        max_active_context_items = scope.get("max_active_context_items")
        max_passive_context_items = scope.get("max_passive_context_items")
        max_archived_context_items = scope.get("max_archived_context_items")
        max_total_context_items = scope.get("max_total_context_items")
        forbidden_phrases = [str(item).strip() for item in (scope.get("forbidden_phrases") or []) if str(item).strip()]

        violations: list[dict[str, Any]] = []
        if isinstance(max_workspace_items, int) and len(workspace_scope) > max_workspace_items:
            violations.append(
                {
                    "rule_id": "HALLUCINATION.WORKSPACE_BUDGET_EXCEEDED",
                    "message": "verification_scope.workspace exceeds configured budget.",
                    "evidence": f"{len(workspace_scope)}>{max_workspace_items}",
                }
            )
        if isinstance(max_active_context_items, int) and len(active_context_scope) > max_active_context_items:
            violations.append(
                {
                    "rule_id": "HALLUCINATION.ACTIVE_CONTEXT_BUDGET_EXCEEDED",
                    "message": "verification_scope.active_context exceeds configured budget.",
                    "evidence": f"{len(active_context_scope)}>{max_active_context_items}",
                }
            )
        if isinstance(max_passive_context_items, int) and len(passive_context_scope) > max_passive_context_items:
            violations.append(
                {
                    "rule_id": "HALLUCINATION.PASSIVE_CONTEXT_BUDGET_EXCEEDED",
                    "message": "verification_scope.passive_context exceeds configured budget.",
                    "evidence": f"{len(passive_context_scope)}>{max_passive_context_items}",
                }
            )
        if isinstance(max_archived_context_items, int) and len(archived_context_scope) > max_archived_context_items:
            violations.append(
                {
                    "rule_id": "HALLUCINATION.ARCHIVED_CONTEXT_BUDGET_EXCEEDED",
                    "message": "verification_scope.archived_context exceeds configured budget.",
                    "evidence": f"{len(archived_context_scope)}>{max_archived_context_items}",
                }
            )
        total_context_items = len(active_context_scope) + len(passive_context_scope) + len(archived_context_scope)
        if isinstance(max_total_context_items, int) and total_context_items > max_total_context_items:
            violations.append(
                {
                    "rule_id": "HALLUCINATION.TOTAL_CONTEXT_BUDGET_EXCEEDED",
                    "message": "verification_scope active+passive+archived exceeds configured total budget.",
                    "evidence": f"{total_context_items}>{max_total_context_items}",
                }
            )

        for call in (turn.tool_calls or []):
            tool_name = str(call.tool or "").strip()
            if declared_interfaces_scope and tool_name and tool_name not in declared_interfaces_scope:
                violations.append(
                    {
                        "rule_id": "HALLUCINATION.API_NOT_DECLARED",
                        "message": f"Tool/API '{tool_name}' not declared in verification scope.",
                        "evidence": tool_name,
                    }
                )

            if tool_name in {"read_file", "write_file"}:
                path = str(call.args.get("path", "")).strip()
                if workspace_scope and path and path not in workspace_scope:
                    violations.append(
                        {
                            "rule_id": "HALLUCINATION.FILE_NOT_FOUND",
                            "message": f"Path '{path}' not present in verification scope.workspace.",
                            "evidence": path,
                        }
                    )

            if tool_name == "get_issue_context":
                ref = str(call.args.get("section", "")).strip()
                if active_context_scope and ref and ref not in active_context_scope:
                    violations.append(
                        {
                            "rule_id": "HALLUCINATION.CONTEXT_NOT_PROVIDED",
                            "message": f"Context reference '{ref}' not present in verification scope.active_context.",
                            "evidence": ref,
                        }
                    )

        content_blob = str(turn.content or "")
        grounding_scan_blob = self.non_json_residue(content_blob)
        if strict_grounding and re.search(r"\b(assume|assumed|probably|maybe)\b", grounding_scan_blob, flags=re.IGNORECASE):
            marker_match = re.search(r"\b(assume|assumed|probably|maybe)\b", grounding_scan_blob, flags=re.IGNORECASE)
            marker = marker_match.group(0) if marker_match else "assume"
            violations.append(
                {
                    "rule_id": "HALLUCINATION.INVENTED_DETAIL",
                    "message": "Output includes speculative language under strict grounding scope.",
                    "evidence": marker,
                }
            )

        lowered_content = content_blob.lower()
        for phrase in forbidden_phrases:
            if phrase.lower() in lowered_content:
                violations.append(
                    {
                        "rule_id": "HALLUCINATION.CONTRADICTION",
                        "message": "Output contradicts a forbidden phrase constraint in verification scope.",
                        "evidence": phrase,
                    }
                )

        return {
            "scope": {
                "workspace": sorted(workspace_scope),
                "provided_context": sorted(active_context_scope),
                "active_context": sorted(active_context_scope),
                "passive_context": sorted(passive_context_scope),
                "archived_context": sorted(archived_context_scope),
                "declared_interfaces": sorted(declared_interfaces_scope),
                "strict_grounding": strict_grounding,
                "max_workspace_items": max_workspace_items,
                "max_active_context_items": max_active_context_items,
                "max_passive_context_items": max_passive_context_items,
                "max_archived_context_items": max_archived_context_items,
                "max_total_context_items": max_total_context_items,
                "forbidden_phrases": forbidden_phrases,
            },
            "violations": violations,
        }

    @staticmethod
    def security_scope_diagnostics(turn: ExecutionTurn, context: dict[str, Any]) -> dict[str, Any]:
        scope = parse_verification_scope(context.get("verification_scope"))
        if not isinstance(scope, dict):
            return {"scope": {}, "violations": []}

        enforce_path_hardening = bool(scope.get("enforce_path_hardening", True))
        violations: list[dict[str, Any]] = []
        if enforce_path_hardening:
            for call in (turn.tool_calls or []):
                tool_name = str(call.tool or "").strip()
                if tool_name not in {"read_file", "write_file", "list_directory", "list_dir"}:
                    continue
                path = str(call.args.get("path", "")).strip()
                if not path:
                    continue
                normalized = path.replace("\\", "/")
                has_traversal = ".." in normalized.split("/")
                is_absolute = normalized.startswith("/") or bool(re.match(r"^[a-zA-Z]:/", normalized))
                if has_traversal or is_absolute:
                    violations.append(
                        {
                            "rule_id": "SECURITY.PATH_TRAVERSAL",
                            "message": f"Path '{path}' violates path hardening constraints.",
                            "evidence": path,
                        }
                    )

        return {"scope": {"enforce_path_hardening": enforce_path_hardening}, "violations": violations}

    def consistency_scope_diagnostics(self, turn: ExecutionTurn, context: dict[str, Any]) -> dict[str, Any]:
        scope = parse_verification_scope(context.get("verification_scope"))
        if not isinstance(scope, dict):
            return {"scope": {}, "violations": []}

        tool_calls_only = bool(scope.get("consistency_tool_calls_only", False))
        if not tool_calls_only:
            return {"scope": {"consistency_tool_calls_only": False}, "violations": []}

        residue = self.non_json_residue(str(turn.content or ""))
        if residue:
            return {
                "scope": {"consistency_tool_calls_only": True},
                "violations": [
                    {
                        "rule_id": "CONSISTENCY.OUTPUT_FORMAT",
                        "message": "Output contains non-JSON prose while tool-calls-only format is required.",
                        "evidence": residue[:120],
                    }
                ],
            }
        return {"scope": {"consistency_tool_calls_only": True}, "violations": []}

    def required_read_paths(self, context: dict[str, Any]) -> list[str]:
        return PathResolver.required_read_paths(context, self.workspace)

    def required_write_paths(self, context: dict[str, Any]) -> list[str]:
        return PathResolver.required_write_paths(context)

    @staticmethod
    def observed_read_paths(turn: ExecutionTurn) -> list[str]:
        return PathResolver.observed_read_paths(turn)

    @staticmethod
    def observed_write_paths(turn: ExecutionTurn) -> list[str]:
        return PathResolver.observed_write_paths(turn)

    def non_json_residue(self, content: str) -> str:
        return self.response_parser.non_json_residue(content)

    def extract_guard_review_payload(self, content: str) -> dict[str, Any]:
        return self.response_parser.extract_guard_review_payload(content)
