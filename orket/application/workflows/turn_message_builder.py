from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.core.domain.verification_scope import parse_verification_scope
from orket.logging import log_event
from orket.schema import IssueConfig, RoleConfig

from .turn_path_resolver import PathResolver


class MessageBuilder:
    """Construct deterministic turn prompt/message payloads."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    async def prepare_messages(
        self,
        *,
        issue: IssueConfig,
        role: RoleConfig,
        context: dict[str, Any],
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        messages.append({"role": "system", "content": system_prompt or role.prompt or role.description})
        messages.append(
            {
                "role": "user",
                "content": f"Issue {issue.id}: {issue.name}\n\nType: {issue.type}\nPriority: {issue.priority}",
            }
        )

        required_read_paths = PathResolver.required_read_paths(context, self.workspace)
        missing_required_read_paths = PathResolver.missing_required_read_paths(context, self.workspace)
        required_write_paths = PathResolver.required_write_paths(context)
        execution_context = {
            "issue_id": context.get("issue_id", issue.id),
            "seat": context.get("role", role.name),
            "status": context.get("current_status"),
            "dependency_context": context.get("dependency_context", {}),
            "execution_profile": context.get("execution_profile"),
            "base_execution_profile": context.get("base_execution_profile"),
            "builder_seat_choice": context.get("builder_seat_choice"),
            "reviewer_seat_choice": context.get("reviewer_seat_choice"),
            "seat_coercion": context.get("seat_coercion", {}),
            "artifact_contract": context.get("artifact_contract", {}),
            "odr_active": bool(context.get("odr_active", False)),
            "required_action_tools": context.get("required_action_tools", []),
            "required_statuses": context.get("required_statuses", []),
            "required_read_paths": required_read_paths,
            "missing_required_read_paths": missing_required_read_paths,
            "required_write_paths": context.get("required_write_paths", []),
            "stage_gate_mode": context.get("stage_gate_mode"),
            "runtime_verifier_ok": context.get("runtime_verifier_ok"),
            "architecture_mode": context.get("architecture_mode"),
            "frontend_framework_mode": context.get("frontend_framework_mode"),
            "architecture_decision_required": bool(context.get("architecture_decision_required")),
            "architecture_decision_path": context.get("architecture_decision_path"),
            "architecture_forced_pattern": context.get("architecture_forced_pattern"),
            "frontend_framework_forced": context.get("frontend_framework_forced"),
            "prompt_metadata": context.get("prompt_metadata", {}),
        }
        messages.append(
            {"role": "user", "content": f"Execution Context JSON:\n{json.dumps(execution_context, sort_keys=True)}"}
        )

        artifact_contract = context.get("artifact_contract")
        if isinstance(artifact_contract, dict) and artifact_contract:
            messages.append(
                {
                    "role": "user",
                    "content": "Artifact Contract JSON:\n" + json.dumps(artifact_contract, sort_keys=True),
                }
            )

        if bool(context.get("odr_active", False)):
            odr_context = {
                "odr_valid": context.get("odr_valid"),
                "odr_pending_decisions": context.get("odr_pending_decisions"),
                "odr_stop_reason": context.get("odr_stop_reason"),
                "odr_artifact_path": context.get("odr_artifact_path"),
            }
            messages.append(
                {
                    "role": "user",
                    "content": "ODR Prebuild Summary JSON:\n" + json.dumps(odr_context, sort_keys=True),
                }
            )
            odr_requirement = str(context.get("odr_requirement") or "").strip()
            if odr_requirement:
                messages.append(
                    {
                        "role": "user",
                        "content": "ODR Refined Requirement:\n" + odr_requirement,
                    }
                )

        if bool(context.get("protocol_governed_enabled", False)):
            protocol_lines = [
                "- Return exactly one JSON object.",
                '- Required envelope: {"content":"","tool_calls":[{"tool":"<tool_name>","args":{"key":"value"}}]}',
                "- content must be an empty string when tool_calls are present.",
                "- Put all required tool calls into tool_calls within that single JSON object.",
                "- Do not use markdown fences or multiple top-level JSON objects.",
            ]
            messages.append({"role": "user", "content": "Protocol Response Contract:\n" + "\n".join(protocol_lines)})

        required_action_tools = [str(t) for t in (context.get("required_action_tools") or []) if t]
        if "read_file" in required_action_tools and not required_read_paths:
            required_action_tools = [tool for tool in required_action_tools if tool != "read_file"]
        read_path_contract_required = "read_file" in required_action_tools
        write_path_contract_required = "write_file" in required_action_tools
        required_statuses = [str(s).strip().lower() for s in (context.get("required_statuses") or []) if s]
        if required_action_tools or required_statuses:
            contract_lines = []
            if required_action_tools:
                contract_lines.append(f"- Required tool calls this turn: {', '.join(required_action_tools)}")
            if required_statuses:
                contract_lines.append(f"- Required update_issue_status.status values: {', '.join(required_statuses)}")
                contract_lines.append(
                    "- If you choose status=blocked, include wait_reason: resource|dependency|review|input|system."
                )
            contract_lines.append("- You must include all required tool calls in this same response.")
            contract_lines.append("- A response containing only get_issue_context/add_issue_comment is invalid.")
            messages.append({"role": "user", "content": "Turn Success Contract:\n" + "\n".join(contract_lines)})

        if required_write_paths and write_path_contract_required:
            write_lines = [
                "- Required write_file paths this turn:",
                *[f"  - {path}" for path in required_write_paths],
                "- Use workspace-relative paths exactly as listed.",
            ]
            messages.append({"role": "user", "content": "Write Path Contract:\n" + "\n".join(write_lines)})

        if required_read_paths and read_path_contract_required:
            read_lines = [
                "- Required read_file paths this turn:",
                *[f"  - {path}" for path in required_read_paths],
                "- Do not use placeholder or absolute paths outside the workspace.",
            ]
            messages.append({"role": "user", "content": "Read Path Contract:\n" + "\n".join(read_lines)})

        should_emit_missing_read_notice = bool(missing_required_read_paths) and read_path_contract_required
        if should_emit_missing_read_notice:
            log_event(
                "preflight_missing_read_paths",
                {
                    "issue_id": issue.id,
                    "role": role.name,
                    "session_id": context.get("session_id", "unknown-session"),
                    "turn_index": int(context.get("turn_index", 0)),
                    "missing_required_read_paths_count": len(missing_required_read_paths),
                    "missing_required_read_paths": missing_required_read_paths,
                },
                self.workspace,
            )
            missing_lines = [
                "- The following expected read paths are currently missing in workspace:",
                *[f"  - {path}" for path in missing_required_read_paths],
                (
                    "- Do not fabricate reads for missing paths; proceed with "
                    "available files and state missing inputs explicitly."
                ),
            ]
            messages.append(
                {
                    "role": "user",
                    "content": "Missing Input Preflight Notice:\n" + "\n".join(missing_lines),
                }
            )

        verification_scope = parse_verification_scope(context.get("verification_scope"))
        if isinstance(verification_scope, dict):
            scope_payload = json.dumps(verification_scope, sort_keys=True)
            messages.append(
                {
                    "role": "user",
                    "content": "Hallucination Verification Scope:\n" + scope_payload,
                }
            )

        if bool(context.get("architecture_decision_required")):
            mode = str(context.get("architecture_mode", "architect_decides"))
            decision_path = str(context.get("architecture_decision_path", "agent_output/design.txt"))
            forced_pattern = str(context.get("architecture_forced_pattern", "") or "").strip().lower()
            forced_frontend_framework = str(context.get("frontend_framework_forced", "") or "").strip().lower()
            allowed_frontend_frameworks = [
                str(v).strip().lower()
                for v in (context.get("frontend_framework_allowed") or ["vue", "react", "angular"])
                if str(v).strip()
            ]
            allowed_patterns = [
                str(v).strip().lower()
                for v in (context.get("architecture_allowed_patterns") or ["monolith", "microservices"])
                if str(v).strip()
            ]
            lines = [
                f"- Write architecture decision JSON to path: {decision_path}",
                f"- recommendation must be one of: {', '.join(allowed_patterns)}",
                "- confidence must be a number between 0 and 1",
                (
                    "- evidence must include keys: estimated_domains, "
                    "external_integrations, independent_scaling_needs, "
                    "deployment_complexity, team_parallelism, operational_maturity"
                ),
                f"- active architecture mode: {mode}",
                f"- frontend_framework should be one of: {', '.join(allowed_frontend_frameworks)}",
            ]
            if forced_pattern:
                lines.append(f"- recommendation MUST equal: {forced_pattern}")
            if forced_frontend_framework:
                lines.append(f"- frontend_framework MUST equal: {forced_frontend_framework}")
            messages.append(
                {
                    "role": "user",
                    "content": "Architecture Decision Contract:\n" + "\n".join(lines),
                }
            )

        if str(context.get("stage_gate_mode", "")).strip().lower() == "review_required":
            runtime_ok = context.get("runtime_verifier_ok")
            runtime_line = "- Runtime verifier result unavailable."
            if runtime_ok is True:
                runtime_line = "- Runtime verifier passed for this issue."
            elif runtime_ok is False:
                runtime_line = "- Runtime verifier failed for this issue."
            blocked_allowed = "blocked" in required_statuses
            if blocked_allowed:
                guard_contract_lines = [
                    "Guard Rejection Contract:",
                    (
                        "- If you set update_issue_status.status to blocked, "
                        "include a second JSON object in the same response."
                    ),
                    '- Required payload schema: {"rationale":"...", "violations":[...], "remediation_actions":[...]}.',
                    "- rationale must be non-empty.",
                    "- violations must contain at least one concrete defect.",
                    "- remediation_actions must contain at least one concrete action.",
                    runtime_line,
                    ("- If runtime verifier passed and no concrete defect is present, choose status=done."),
                ]
            else:
                guard_contract_lines = [
                    "Guard Decision Contract:",
                    runtime_line,
                    "- This turn only allows update_issue_status.status=done.",
                    "- Do not emit blocked for this turn.",
                ]
            messages.append(
                {
                    "role": "user",
                    "content": "\n".join(guard_contract_lines),
                }
            )

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

        return messages
