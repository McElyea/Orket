"""Render the captured issue, protocol, architecture and history prompt sections."""
from __future__ import annotations

import json
from typing import Any

from orket.application.services.card_completion_prompt import guard_review_contract_lines
from orket.core.domain.verification_scope import parse_verification_scope
from orket.schema import IssueConfig, RoleConfig

from .turn_artifact_destination import TurnArtifactDestination
from .turn_message_execution_context import build_message_execution_context
from .turn_path_resolver import PathResolver


def initial_messages(
    issue: IssueConfig,
    role: RoleConfig,
    context: dict[str, Any],
    destination: TurnArtifactDestination,
    system_prompt: str | None,
    required_read_paths: list[str],
    missing_required_read_paths: list[str],
) -> tuple[list[dict[str, str]], dict[str, str] | None, list[str]]:
    messages: list[dict[str, str]] = []
    messages.append({"role": "system", "content": system_prompt or role.prompt or role.description})
    messages.append(
        {
            "role": "user",
            "content": f"Issue {destination.issue_id}: {issue.name}\n\nType: {issue.type}\nPriority: {issue.priority}",
        }
    )
    role_name = destination.role_name.lower()
    current_status = str(context.get("current_status", "") or "").strip().lower()
    is_guard_review_turn = role_name == "integrity_guard" or current_status == "awaiting_guard_review"
    issue_brief_message: dict[str, str] | None = None
    if not is_guard_review_turn:
        issue_brief_lines: list[str] = []
        description = str(getattr(issue, "description", "") or "").strip()
        if description:
            issue_brief_lines.append(f"Description: {description}")
        requirements = str(getattr(issue, "requirements", "") or "").strip()
        if requirements:
            issue_brief_lines.append(f"Requirements: {requirements}")
        note = str(getattr(issue, "note", "") or "").strip()
        if note:
            issue_brief_lines.append(f"Task Note: {note}")
        retry_note = str(context.get("runtime_retry_note") or "").strip()
        if retry_note:
            issue_brief_lines.append(f"Retry Note: {retry_note}")
        references = [str(item).strip() for item in getattr(issue, "references", []) or [] if str(item).strip()]
        if references:
            issue_brief_lines.append("References:")
            issue_brief_lines.extend(f"- {reference}" for reference in references)
        if issue_brief_lines:
            issue_brief_message = {"role": "user", "content": "Issue Brief:\n" + "\n".join(issue_brief_lines)}
    required_write_paths = PathResolver.required_write_paths(context)
    execution_context = build_message_execution_context(
        destination=destination,
        context=context,
        required_read_paths=required_read_paths,
        missing_required_read_paths=missing_required_read_paths,
    )
    messages.append(
        {"role": "user", "content": f"Execution Context JSON:\n{json.dumps(execution_context, sort_keys=True)}"}
    )
    return (messages, issue_brief_message, required_write_paths)


def append_protocol_context(messages: list[dict[str, str]], context: dict[str, Any]) -> None:
    if bool(context.get("odr_active", False)):
        odr_context = {
            "odr_valid": context.get("odr_valid"),
            "odr_pending_decisions": context.get("odr_pending_decisions"),
            "odr_stop_reason": context.get("odr_stop_reason"),
            "odr_termination_reason": context.get("odr_termination_reason"),
            "odr_final_auditor_verdict": context.get("odr_final_auditor_verdict"),
            "odr_artifact_path": context.get("odr_artifact_path"),
        }
        messages.append(
            {"role": "user", "content": "ODR Prebuild Summary JSON:\n" + json.dumps(odr_context, sort_keys=True)}
        )
        odr_requirement = str(context.get("odr_requirement") or "").strip()
        if odr_requirement:
            messages.append({"role": "user", "content": "ODR Refined Requirement:\n" + odr_requirement})
    if bool(context.get("protocol_governed_enabled", False)):
        protocol_lines = [
            "- Return exactly one JSON object.",
            '- Required envelope: {"content":"","tool_calls":[{"tool":"<tool_name>","args":{"key":"value"}}]}',
            "- content must be an empty string when tool_calls are present.",
            "- Put all required tool calls into tool_calls within that single JSON object.",
            "- Do not use markdown fences or multiple top-level JSON objects.",
        ]
        messages.append({"role": "user", "content": "Protocol Response Contract:\n" + "\n".join(protocol_lines)})


def append_verification_scope(messages: list[dict[str, str]], context: dict[str, Any]) -> None:
    verification_scope = parse_verification_scope(context.get("verification_scope"))
    if isinstance(verification_scope, dict):
        scope_payload = json.dumps(verification_scope, sort_keys=True)
        messages.append({"role": "user", "content": "Hallucination Verification Scope:\n" + scope_payload})


def append_architecture_contract(messages: list[dict[str, str]], context: dict[str, Any]) -> None:
    if bool(context.get("architecture_decision_required")):
        mode = str(context.get("architecture_mode", "architect_decides"))
        decision_path = str(context.get("architecture_decision_path", "agent_output/design.txt"))
        forced_pattern = str(context.get("architecture_forced_pattern", "") or "").strip().lower()
        forced_frontend_framework = str(context.get("frontend_framework_forced", "") or "").strip().lower()
        allowed_frontend_frameworks = [
            str(v).strip().lower()
            for v in context.get("frontend_framework_allowed") or ["vue", "react", "angular"]
            if str(v).strip()
        ]
        allowed_patterns = [
            str(v).strip().lower()
            for v in context.get("architecture_allowed_patterns") or ["monolith", "microservices"]
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
        messages.append({"role": "user", "content": "Architecture Decision Contract:\n" + "\n".join(lines)})


def append_review_and_history(
    messages: list[dict[str, str]], context: dict[str, Any], required_statuses: list[str]
) -> None:
    if str(context.get("stage_gate_mode", "")).strip().lower() == "review_required":
        messages.append({"role": "user", "content": "\n".join(guard_review_contract_lines(context, required_statuses))})
    history_rows = context.get("history")
    if isinstance(history_rows, list) and history_rows:
        history_payload: list[dict[str, str]] = []
        for row in history_rows:
            if not isinstance(row, dict):
                continue
            actor = str(row.get("role", "")).strip()
            content = str(row.get("content", "")).strip()
            if not content:
                continue
            history_payload.append({"actor": actor, "content": content})
        if history_payload:
            messages.append(
                {
                    "role": "user",
                    "content": "Prior Transcript JSON:\n" + json.dumps(history_payload, ensure_ascii=False),
                }
            )
