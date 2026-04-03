from __future__ import annotations
import hashlib
from pathlib import Path
import re
from typing import Any
from orket.domain.execution import ExecutionTurn
from orket.runtime.error_codes import (
    ERR_JSON_MD_FENCE,
    ERR_THINK_OVERFLOW,
    EXTRANEOUS_TEXT,
    error_family_for_leaf,
)
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
from .turn_artifact_semantic_rules import artifact_semantic_contract_diagnostics
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
        empty_write_paths = self.empty_required_write_paths(turn, context)
        if empty_write_paths:
            violations.append(
                {
                    "reason": "write_content_contract_not_met",
                    "empty_required_write_paths": empty_write_paths,
                }
            )
        semantic_diag = artifact_semantic_contract_diagnostics(turn, context)
        if semantic_diag.get("violations"):
            violations.append(
                {
                    "reason": "artifact_semantic_contract_not_met",
                    "violations": semantic_diag.get("violations", []),
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
        comment_diag = self.comment_contract_diagnostics(turn, context)
        if not comment_diag.get("ok", False):
            violations.append(
                {
                    "reason": "comment_contract_not_met",
                    "required_comment_min_length": comment_diag.get("required_comment_min_length"),
                    "required_comment_contains": comment_diag.get("required_comment_contains", []),
                    "observed_comment_lengths": comment_diag.get("observed_comment_lengths", []),
                    "missing_comment_terms": comment_diag.get("missing_comment_terms", []),
                    "missing_comment_paths": comment_diag.get("missing_comment_paths", []),
                }
            )
        anti_meta = self.local_prompt_anti_meta_diagnostics(turn, context)
        if anti_meta.get("violations"):
            violations.append(
                {
                    "reason": "local_prompt_anti_meta_contract_not_met",
                    "violations": anti_meta.get("violations", []),
                    "task_class": anti_meta.get("task_class"),
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
        required_statuses = {
            str(status).strip().lower() for status in (context.get("required_statuses") or []) if status
        }
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
        required_tools = {str(tool).strip() for tool in (context.get("required_action_tools") or []) if str(tool).strip()}
        if "write_file" not in required_tools:
            return True
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
        required_tools = {str(tool).strip() for tool in (context.get("required_action_tools") or []) if str(tool).strip()}
        if "read_file" not in required_tools:
            return True
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

    def empty_required_write_paths(self, turn: ExecutionTurn, context: dict[str, Any]) -> list[str]:
        required_tools = {str(tool).strip() for tool in (context.get("required_action_tools") or []) if str(tool).strip()}
        if "write_file" not in required_tools:
            return []
        required_paths = set(self.required_write_paths(context))
        if not required_paths:
            return []
        empty_paths: list[str] = []
        for call in turn.tool_calls or []:
            if call.tool != "write_file":
                continue
            path = str((call.args or {}).get("path") or "").strip()
            if path not in required_paths:
                continue
            content = (call.args or {}).get("content")
            if not isinstance(content, str) or not content.strip():
                empty_paths.append(path)
        return empty_paths

    def comment_contract_diagnostics(self, turn: ExecutionTurn, context: dict[str, Any]) -> dict[str, Any]:
        required_tools = {str(tool).strip() for tool in (context.get("required_action_tools") or []) if str(tool).strip()}
        required_comment_contains = [
            str(token).strip()
            for token in (context.get("required_comment_contains") or [])
            if str(token).strip()
        ]
        raw_min_length = context.get("required_comment_min_length")
        required_comment_min_length = None
        if raw_min_length is not None:
            try:
                required_comment_min_length = max(1, int(raw_min_length))
            except (TypeError, ValueError):
                required_comment_min_length = None

        comment_payloads = [
            str(call.args.get("comment", "") or "").strip()
            for call in (turn.tool_calls or [])
            if call.tool == "add_issue_comment"
        ]
        required_comment_paths = self.required_read_paths(context)
        observed_comment_lengths = [len(comment) for comment in comment_payloads]
        enforcement_required = (
            "add_issue_comment" in required_tools
            or required_comment_min_length is not None
            or bool(required_comment_contains)
        )
        if not enforcement_required:
            return {
                "ok": True,
                "required_comment_min_length": required_comment_min_length,
                "required_comment_contains": required_comment_contains,
                "observed_comment_lengths": observed_comment_lengths,
                "missing_comment_terms": [],
                "missing_comment_paths": [],
            }
        if not comment_payloads:
            return {
                "ok": False,
                "required_comment_min_length": required_comment_min_length,
                "required_comment_contains": required_comment_contains,
                "observed_comment_lengths": [],
                "missing_comment_terms": required_comment_contains,
                "missing_comment_paths": required_comment_paths,
            }

        for comment in comment_payloads:
            if required_comment_min_length is not None and len(comment) < required_comment_min_length:
                continue
            lower_comment = comment.lower()
            missing_terms = [
                token for token in required_comment_contains if token.lower() not in lower_comment
            ]
            missing_paths = [path for path in required_comment_paths if path.lower() not in lower_comment]
            if not missing_terms and not missing_paths:
                return {
                    "ok": True,
                    "required_comment_min_length": required_comment_min_length,
                    "required_comment_contains": required_comment_contains,
                    "observed_comment_lengths": observed_comment_lengths,
                    "missing_comment_terms": [],
                    "missing_comment_paths": [],
                }

        longest_comment = max(comment_payloads, key=len)
        lower_longest = longest_comment.lower()
        missing_terms = [
            token for token in required_comment_contains if token.lower() not in lower_longest
        ]
        missing_paths = [path for path in required_comment_paths if path.lower() not in lower_longest]
        return {
            "ok": False,
            "required_comment_min_length": required_comment_min_length,
            "required_comment_contains": required_comment_contains,
            "observed_comment_lengths": observed_comment_lengths,
            "missing_comment_terms": missing_terms,
            "missing_comment_paths": missing_paths,
        }

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

    @staticmethod
    def _trim_ascii_whitespace_once(content: str) -> tuple[str, str]:
        allowed = {" ", "\t", "\n", "\r"}
        if content and content[0].isspace() and content[0] not in allowed:
            return content, "non-ascii leading whitespace"
        if content and content[-1].isspace() and content[-1] not in allowed:
            return content, "non-ascii trailing whitespace"
        start = 0
        end = len(content)
        while start < end and content[start] in allowed:
            start += 1
        while end > start and content[end - 1] in allowed:
            end -= 1
        return content[start:end], ""

    @staticmethod
    def _resolve_intro_denylist(raw: dict[str, Any], context: dict[str, Any]) -> list[str]:
        source = (
            raw.get("local_prompt_intro_denylist")
            or raw.get("intro_phrase_denylist")
            or context.get("local_prompt_intro_denylist")
            or []
        )
        if not isinstance(source, list):
            return []
        return [str(item).strip().lower() for item in source if str(item).strip()]

    @staticmethod
    def _local_prompt_violation(
        *,
        rule_id: str,
        detail: str,
        excerpt: str,
        error_code: str = "",
        error_family: str = EXTRANEOUS_TEXT,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rule_id": rule_id,
            "detail": detail,
            "error_family": error_family,
            "short_error_detail": detail[:120],
            "prior_output_excerpt_hash": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        }
        if error_code:
            payload["error_code"] = error_code
        return payload

    def local_prompt_anti_meta_diagnostics(self, turn: ExecutionTurn, context: dict[str, Any]) -> dict[str, Any]:
        raw = turn.raw if isinstance(turn.raw, dict) else {}
        task_class = str(context.get("local_prompt_task_class") or raw.get("task_class") or "").strip().lower()
        if task_class not in {"strict_json", "tool_call"}:
            return {"task_class": task_class, "violations": []}
        protocol_governed_enabled = bool(context.get("protocol_governed_enabled", False))
        content = str(turn.content or "")
        trimmed, trim_error = self._trim_ascii_whitespace_once(content)
        violations: list[dict[str, Any]] = []
        if trim_error:
            violations.append(
                self._local_prompt_violation(
                    rule_id="LOCAL_PROMPT.ASCII_WHITESPACE",
                    detail=trim_error,
                    excerpt=content[:240],
                )
            )
        if protocol_governed_enabled and "```" in content:
            violations.append(
                self._local_prompt_violation(
                    rule_id="LOCAL_PROMPT.MARKDOWN_FENCE",
                    detail="markdown fence detected",
                    excerpt=content[:240],
                    error_code=ERR_JSON_MD_FENCE,
                    error_family=error_family_for_leaf(ERR_JSON_MD_FENCE) or EXTRANEOUS_TEXT,
                )
            )
        allows_thinking = bool(
            raw.get("local_prompt_allows_thinking_blocks")
            if raw.get("local_prompt_allows_thinking_blocks") is not None
            else raw.get("allows_thinking_blocks", context.get("local_prompt_allows_thinking_blocks", False))
        )
        thinking_format = str(
            raw.get("local_prompt_thinking_block_format")
            or raw.get("thinking_block_format")
            or context.get("local_prompt_thinking_block_format")
            or "none"
        ).strip()
        sanitized = trimmed
        has_think_markers = bool(re.search(r"<\s*/?\s*think\b", trimmed, flags=re.IGNORECASE))
        if has_think_markers and not allows_thinking:
            violations.append(
                self._local_prompt_violation(
                    rule_id="LOCAL_PROMPT.THINK_FORBIDDEN",
                    detail="thinking markers are not allowed",
                    excerpt=content[:240],
                    error_code=ERR_THINK_OVERFLOW,
                    error_family=error_family_for_leaf(ERR_THINK_OVERFLOW) or EXTRANEOUS_TEXT,
                )
            )
        if has_think_markers and allows_thinking:
            sanitized, block_count = self.response_parser.strip_leading_thinking_blocks(trimmed, thinking_format)
            if block_count == 0 or re.search(r"<\s*/?\s*think\b", sanitized, flags=re.IGNORECASE):
                violations.append(
                    self._local_prompt_violation(
                        rule_id="LOCAL_PROMPT.THINK_POSITION",
                        detail="thinking block appears after payload start or is malformed",
                        excerpt=content[:240],
                        error_code=ERR_THINK_OVERFLOW,
                        error_family=error_family_for_leaf(ERR_THINK_OVERFLOW) or EXTRANEOUS_TEXT,
                    )
                )
        denylist = self._resolve_intro_denylist(raw, context)
        lowered = sanitized.strip().lower()
        for token in denylist:
            if lowered.startswith(token):
                violations.append(
                    self._local_prompt_violation(
                        rule_id="LOCAL_PROMPT.INTRO_DENYLIST",
                        detail=token,
                        excerpt=sanitized[:240],
                    )
                )
                break
        residue = self.non_json_residue(sanitized)
        if residue:
            violations.append(
                self._local_prompt_violation(
                    rule_id="LOCAL_PROMPT.EXTRANEOUS_TEXT",
                    detail=residue[:120],
                    excerpt=sanitized[:240],
                )
            )
        return {"task_class": task_class, "violations": violations}
