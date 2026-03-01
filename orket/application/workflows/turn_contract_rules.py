from __future__ import annotations

import json
import re
from typing import Any, Callable

from orket.core.domain.verification_scope import parse_verification_scope
from orket.domain.execution import ExecutionTurn

from .turn_path_resolver import PathResolver


def parse_architecture_decision_payload(raw_content: str) -> dict[str, Any] | None:
    from orket.application.services.tool_parser import ToolParser

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


def meets_architecture_decision_contract(turn: ExecutionTurn, context: dict[str, Any]) -> bool:
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
        payload = parse_architecture_decision_payload(raw_content)
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


def hallucination_scope_diagnostics(
    turn: ExecutionTurn,
    context: dict[str, Any],
    non_json_residue: Callable[[str], str],
) -> dict[str, Any]:
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
    grounding_scan_blob = non_json_residue(content_blob)
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


def consistency_scope_diagnostics(
    turn: ExecutionTurn,
    context: dict[str, Any],
    non_json_residue: Callable[[str], str],
) -> dict[str, Any]:
    scope = parse_verification_scope(context.get("verification_scope"))
    if not isinstance(scope, dict):
        return {"scope": {}, "violations": []}

    tool_calls_only = bool(scope.get("consistency_tool_calls_only", False))
    if not tool_calls_only:
        return {"scope": {"consistency_tool_calls_only": False}, "violations": []}

    residue = non_json_residue(str(turn.content or ""))
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


def required_read_paths(context: dict[str, Any], workspace: Any) -> list[str]:
    return PathResolver.required_read_paths(context, workspace)


def required_write_paths(context: dict[str, Any]) -> list[str]:
    return PathResolver.required_write_paths(context)


def observed_read_paths(turn: ExecutionTurn) -> list[str]:
    return PathResolver.observed_read_paths(turn)


def observed_write_paths(turn: ExecutionTurn) -> list[str]:
    return PathResolver.observed_write_paths(turn)
