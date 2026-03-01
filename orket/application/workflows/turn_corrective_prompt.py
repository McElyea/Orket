from __future__ import annotations

from pathlib import Path

from .turn_path_resolver import PathResolver


class CorrectivePromptBuilder:
    """Build deterministic corrective prompts for contract violations."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def build_corrective_instruction(self, violations: list[dict], context: dict) -> str:
        lines = [
            "Corrective instruction: previous response violated deterministic turn contracts.",
            "Return JSON tool-call blocks only and satisfy all required contracts in this same response.",
        ]
        reason_set = {
            str(item.get("reason", "")).strip()
            for item in violations
            if str(item.get("reason", "")).strip()
        }
        if "progress_contract_not_met" in reason_set:
            required_action_tools = [str(t) for t in (context.get("required_action_tools") or []) if str(t).strip()]
            required_statuses = [
                str(s).strip().lower() for s in (context.get("required_statuses") or []) if str(s).strip()
            ]
            if required_action_tools:
                lines.append(f"- Required tools this turn: {', '.join(required_action_tools)}.")
            if required_statuses:
                lines.append("- Required update_issue_status values: " + ", ".join(required_statuses) + ".")
                if "blocked" in required_statuses:
                    lines.append(
                        "- If status=blocked, include wait_reason in: resource|dependency|review|input|system."
                    )

        if "write_path_contract_not_met" in reason_set:
            required_write_paths = PathResolver.required_write_paths(context)
            if required_write_paths:
                lines.append("- Required write_file paths:")
                for path in required_write_paths:
                    lines.append(f"  - {path}")

        if "read_path_contract_not_met" in reason_set:
            required_read_paths = PathResolver.required_read_paths(context, self.workspace)
            if required_read_paths:
                lines.append("- Required read_file paths:")
                for path in required_read_paths:
                    lines.append(f"  - {path}")

        if "architecture_decision_contract_not_met" in reason_set:
            lines.append(
                "- Architecture decision JSON is required at the configured architecture_decision_path "
                "with recommendation, confidence (0..1), and full evidence keys."
            )
        if "guard_rejection_payload_contract_not_met" in reason_set:
            lines.append(
                "- If update_issue_status.status=blocked, include JSON payload keys: "
                "rationale (non-empty), violations (non-empty list), remediation_actions (non-empty list)."
            )
        if "hallucination_scope_contract_not_met" in reason_set:
            lines.append("- Do not reference files, tools, APIs, or context outside Hallucination Verification Scope.")
            lines.append("- If scope data is missing, say it is missing instead of guessing or inventing references.")
        if "security_scope_contract_not_met" in reason_set:
            lines.append("- Security guard failed: use only workspace-relative paths and avoid path traversal patterns.")
            lines.append("- Do not use absolute paths or '..' segments in tool arguments.")
        if "consistency_scope_contract_not_met" in reason_set:
            lines.append("- Consistency guard failed: output tool-call JSON only with no extra prose.")
            lines.append("- Keep response format deterministic and schema-compliant.")

        rule_hints = self.rule_specific_fix_hints(violations)
        if rule_hints:
            lines.append("- Rule-specific fixes:")
            for hint in rule_hints:
                lines.append(f"  - {hint}")

        required_read_paths = PathResolver.required_read_paths(context, self.workspace)
        required_write_paths = PathResolver.required_write_paths(context)
        required_statuses = [
            str(s).strip().lower() for s in (context.get("required_statuses") or []) if str(s).strip()
        ]
        if required_read_paths or required_write_paths or required_statuses:
            lines.append("- Required-call template (emit blocks like these in this same response):")
            for path in required_read_paths:
                lines.append(f'  {{"tool":"read_file","args":{{"path":"{path}"}}}}')
            for path in required_write_paths:
                lines.append(f'  {{"tool":"write_file","args":{{"path":"{path}","content":"<actual content>"}}}}')
            if len(required_statuses) == 1:
                status = required_statuses[0]
                if status == "blocked":
                    lines.append(
                        '  {"tool":"update_issue_status","args":{"status":"blocked","wait_reason":"review"}}'
                    )
                else:
                    lines.append(f'  {{"tool":"update_issue_status","args":{{"status":"{status}"}}}}')
            elif required_statuses:
                lines.append(
                    "  "
                    + '{"tool":"update_issue_status","args":{"status":"<one of '
                    + "|".join(required_statuses)
                    + '>"}}'
                )

        return "\n".join(lines)

    def rule_specific_fix_hints(self, violations: list[dict]) -> list[str]:
        hints: list[str] = []
        for item in violations:
            nested = item.get("violations")
            if not isinstance(nested, list):
                continue
            for violation in nested:
                if not isinstance(violation, dict):
                    continue
                rule_id = str(violation.get("rule_id", "")).strip().upper()
                evidence = str(violation.get("evidence", "")).strip()
                if not rule_id:
                    continue
                hint = self.hint_for_rule_id(rule_id, evidence)
                if hint:
                    hints.append(hint)
        deduped: list[str] = []
        seen: set[str] = set()
        for hint in hints:
            if hint in seen:
                continue
            seen.add(hint)
            deduped.append(hint)
        return deduped

    def hint_for_rule_id(self, rule_id: str, evidence: str) -> str:
        mapping = {
            "SECURITY.PATH_TRAVERSAL": "SECURITY.PATH_TRAVERSAL: use workspace-relative paths only and remove '..' or absolute prefixes.",
            "HALLUCINATION.FILE_NOT_FOUND": "HALLUCINATION.FILE_NOT_FOUND: reference only files listed in verification_scope.workspace.",
            "HALLUCINATION.API_NOT_DECLARED": "HALLUCINATION.API_NOT_DECLARED: call only tools listed in verification_scope.declared_interfaces.",
            "HALLUCINATION.CONTEXT_NOT_PROVIDED": "HALLUCINATION.CONTEXT_NOT_PROVIDED: reference only verification_scope.active_context entries.",
            "HALLUCINATION.INVENTED_DETAIL": "HALLUCINATION.INVENTED_DETAIL: remove speculative language and state missing information explicitly.",
            "HALLUCINATION.CONTRADICTION": "HALLUCINATION.CONTRADICTION: remove statements that match forbidden phrase constraints.",
            "HALLUCINATION.WORKSPACE_BUDGET_EXCEEDED": "HALLUCINATION.WORKSPACE_BUDGET_EXCEEDED: reduce workspace scope entries to configured budget.",
            "HALLUCINATION.ACTIVE_CONTEXT_BUDGET_EXCEEDED": "HALLUCINATION.ACTIVE_CONTEXT_BUDGET_EXCEEDED: trim active context to the configured limit.",
            "HALLUCINATION.PASSIVE_CONTEXT_BUDGET_EXCEEDED": "HALLUCINATION.PASSIVE_CONTEXT_BUDGET_EXCEEDED: trim passive context to the configured limit.",
            "HALLUCINATION.ARCHIVED_CONTEXT_BUDGET_EXCEEDED": "HALLUCINATION.ARCHIVED_CONTEXT_BUDGET_EXCEEDED: trim archived context to the configured limit.",
            "HALLUCINATION.TOTAL_CONTEXT_BUDGET_EXCEEDED": "HALLUCINATION.TOTAL_CONTEXT_BUDGET_EXCEEDED: reduce total active+passive+archived context size.",
            "CONSISTENCY.OUTPUT_FORMAT": "CONSISTENCY.OUTPUT_FORMAT: emit JSON tool-call objects only with no prose residue.",
        }
        base = mapping.get(rule_id) or f"{rule_id}: address this contract violation deterministically."
        if evidence:
            return f"{base} Evidence: {evidence}"
        return base

    @staticmethod
    def deterministic_failure_message(reason: str) -> str:
        reason_key = str(reason or "").strip().lower()
        mapping = {
            "progress_contract_not_met": "Deterministic failure: progress contract not met after corrective reprompt.",
            "guard_rejection_payload_contract_not_met": "Deterministic failure: guard rejection payload contract not met after corrective reprompt.",
            "read_path_contract_not_met": "Deterministic failure: read path contract not met after corrective reprompt.",
            "write_path_contract_not_met": "Deterministic failure: write path contract not met after corrective reprompt.",
            "architecture_decision_contract_not_met": "Deterministic failure: architecture decision contract not met after corrective reprompt.",
            "hallucination_scope_contract_not_met": "Deterministic failure: hallucination scope contract not met after corrective reprompt.",
            "security_scope_contract_not_met": "Deterministic failure: security scope contract not met after corrective reprompt.",
            "consistency_scope_contract_not_met": "Deterministic failure: consistency scope contract not met after corrective reprompt.",
        }
        return mapping.get(reason_key, "Deterministic failure: turn contract not met after corrective reprompt.")
