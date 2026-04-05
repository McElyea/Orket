from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import aiofiles

from orket.core.domain.verification_scope import parse_verification_scope
from orket.logging import log_event
from orket.runtime.compact_turn_packet import compact_turn_messages
from orket.schema import IssueConfig, RoleConfig

from .turn_artifact_semantic_prompt_hints import artifact_semantic_exact_shape_hints
from .turn_path_resolver import PathResolver

_MAX_PRELOADED_READ_CONTEXT_CHARS = 4000


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

        role_name = str(context.get("role", role.name) or role.name).strip().lower()
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
            references = [str(item).strip() for item in (getattr(issue, "references", []) or []) if str(item).strip()]
            if references:
                issue_brief_lines.append("References:")
                issue_brief_lines.extend(f"- {reference}" for reference in references)
            if issue_brief_lines:
                issue_brief_message = {"role": "user", "content": "Issue Brief:\n" + "\n".join(issue_brief_lines)}

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
            "profile_traits": context.get("profile_traits", {}),
            "seat_coercion": context.get("seat_coercion", {}),
            "artifact_contract": context.get("artifact_contract", {}),
            "scenario_truth": context.get("scenario_truth", {}),
            "odr_active": bool(context.get("odr_active", False)),
            "required_action_tools": context.get("required_action_tools", []),
            "required_statuses": context.get("required_statuses", []),
            "required_read_paths": required_read_paths,
            "missing_required_read_paths": missing_required_read_paths,
            "required_write_paths": context.get("required_write_paths", []),
            "required_comment_min_length": context.get("required_comment_min_length"),
            "required_comment_contains": context.get("required_comment_contains", []),
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
        profile_traits = context.get("profile_traits")
        if isinstance(profile_traits, dict):
            profile_traits = dict(profile_traits)
        else:
            profile_traits = {}
        artifact_contract_allowed = bool(profile_traits.get("artifact_contract_required", True))
        runtime_verifier_allowed = bool(profile_traits.get("runtime_verifier_allowed", True))
        profile_intent = str(profile_traits.get("intent") or "").strip().lower()

        if (
            artifact_contract_allowed
            and isinstance(artifact_contract, dict)
            and artifact_contract
            and str(artifact_contract.get("kind") or "").strip().lower() != "none"
        ):
            messages.append(
                {
                    "role": "user",
                    "content": "Artifact Contract JSON:\n" + json.dumps(artifact_contract, sort_keys=True),
                }
            )
            semantic_checks = artifact_contract.get("semantic_checks")
            if isinstance(semantic_checks, list) and semantic_checks:
                semantic_lines = [
                    "- Additional semantic checks apply to written artifact paths.",
                    "- Every listed Must contain token is checked as an exact substring; include each one verbatim in the final file content.",
                    "- Every listed Must not contain token is also checked as an exact substring; remove each one verbatim from the final file content.",
                ]
                exact_shape_hints: list[str] = []
                seen_exact_shape_hints: set[str] = set()
                for raw_check in semantic_checks:
                    if not isinstance(raw_check, dict):
                        continue
                    path = str(raw_check.get("path") or "").strip()
                    label = str(raw_check.get("label") or "").strip()
                    if path:
                        semantic_lines.append(f"- Path: {path}")
                    if label:
                        semantic_lines.append(f"  - Purpose: {label}")
                    must_contain = [
                        str(token).strip()
                        for token in (raw_check.get("must_contain") or [])
                        if str(token).strip()
                    ]
                    if must_contain:
                        semantic_lines.append("  - Must contain: " + ", ".join(must_contain))
                    must_not_contain = [
                        str(token).strip()
                        for token in (raw_check.get("must_not_contain") or [])
                        if str(token).strip()
                    ]
                    if must_not_contain:
                        semantic_lines.append("  - Must not contain: " + ", ".join(must_not_contain))
                    for hint in artifact_semantic_exact_shape_hints(
                        path=path,
                        must_contain=must_contain,
                        must_not_contain=must_not_contain,
                    ):
                        if hint in seen_exact_shape_hints:
                            continue
                        seen_exact_shape_hints.add(hint)
                        exact_shape_hints.append(hint)
                messages.append(
                    {
                        "role": "user",
                        "content": "Artifact Semantic Contract:\n" + "\n".join(semantic_lines),
                    }
                )
                if exact_shape_hints:
                    messages.append(
                        {
                            "role": "user",
                            "content": "Artifact Exact-Shape Hints:\n" + "\n".join(exact_shape_hints),
                        }
                    )
        scenario_truth = context.get("scenario_truth")
        if isinstance(scenario_truth, dict) and scenario_truth:
            blocked_issue_policy = (
                scenario_truth.get("blocked_issue_policy")
                if isinstance(scenario_truth.get("blocked_issue_policy"), dict)
                else {}
            )
            allowed_issue_ids = [
                str(token).strip()
                for token in (blocked_issue_policy.get("allowed_issue_ids") or [])
                if str(token).strip()
            ]
            scenario_lines = [
                f"- scenario_id: {str(scenario_truth.get('scenario_id') or '').strip()}",
                "- blocked_issue_policy.allowed_issue_ids: "
                + (", ".join(allowed_issue_ids) if allowed_issue_ids else "none"),
                "- blocked_issue_policy.blocked_implies_run_failure: "
                + str(bool(blocked_issue_policy.get("blocked_implies_run_failure"))).lower(),
            ]
            expected_terminal_status = str(scenario_truth.get("expected_terminal_status") or "").strip()
            if expected_terminal_status:
                scenario_lines.append(f"- expected_terminal_status: {expected_terminal_status}")
            expected_truth_classification = str(scenario_truth.get("expected_truth_classification") or "").strip()
            if expected_truth_classification:
                scenario_lines.append(f"- expected_truth_classification: {expected_truth_classification}")
            if issue.id in allowed_issue_ids:
                scenario_lines.append("- This issue is one of the admitted blocked_issue_policy.allowed_issue_ids.")
            messages.append({"role": "user", "content": "Scenario Truth Contract:\n" + "\n".join(scenario_lines)})
        runtime_verifier_contract = context.get("runtime_verifier_contract")
        if isinstance(runtime_verifier_contract, dict):
            runtime_verifier_contract = dict(runtime_verifier_contract)
        else:
            runtime_verifier_contract = {}
        runtime_verifier_prompt_enabled = runtime_verifier_allowed or (
            bool(runtime_verifier_contract) and profile_intent in {"write_artifact", "build_app"}
        )
        if (
            runtime_verifier_prompt_enabled
            and isinstance(artifact_contract, dict)
            and artifact_contract
            and str(artifact_contract.get("kind") or "").strip().lower() != "none"
        ):
            entrypoint_path = str(artifact_contract.get("entrypoint_path") or "").strip()
            artifact_kind = str(artifact_contract.get("kind") or "").strip().lower()
            verifier_lines: list[str] = []
            explicit_commands = runtime_verifier_contract.get("commands")
            if isinstance(explicit_commands, list) and explicit_commands:
                verifier_lines.append("- The runtime verifier will execute these commands exactly:")
                for raw_command in explicit_commands:
                    cwd = "."
                    argv = raw_command
                    if isinstance(raw_command, dict):
                        cwd = str(raw_command.get("cwd") or ".").strip() or "."
                        argv = raw_command.get("argv")
                    if not isinstance(argv, list):
                        continue
                    rendered = " ".join(str(token).strip() for token in argv if str(token).strip())
                    if not rendered:
                        continue
                    verifier_lines.append(f"  - cwd={cwd}: {rendered}")
            if artifact_kind == "app" and entrypoint_path:
                verifier_lines.append(f"- The runtime verifier will execute exactly: python {entrypoint_path}")
                verifier_lines.append("- The entrypoint must succeed with no positional arguments or interactive input.")
                verifier_lines.append("- The entrypoint runs as a script, so do not use package-relative imports in that file.")
            if bool(runtime_verifier_contract.get("expect_json_stdout", False)):
                verifier_lines.append("- The verifier command checked for stdout must print valid JSON.")
            json_assertions = runtime_verifier_contract.get("json_assertions")
            if isinstance(json_assertions, list) and json_assertions:
                verifier_lines.append("- Required stdout assertions:")
                for assertion in json_assertions:
                    if not isinstance(assertion, dict):
                        continue
                    path = str(assertion.get("path") or "").strip()
                    op = str(assertion.get("op") or "").strip()
                    value = assertion.get("value")
                    if not path or not op:
                        continue
                    verifier_lines.append(f"  - {path} {op} {value!r}")
            if verifier_lines:
                messages.append(
                    {
                        "role": "user",
                        "content": "Runtime Verifier Contract:\n" + "\n".join(verifier_lines),
                    }
                )
        if issue_brief_message is not None:
            messages.append(issue_brief_message)

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
        profile_intent = str(((context.get("profile_traits") or {}) if isinstance(context.get("profile_traits"), dict) else {}).get("intent") or "").strip().lower()
        required_statuses = [str(s).strip().lower() for s in (context.get("required_statuses") or []) if s]
        required_comment_min_length = context.get("required_comment_min_length")
        required_comment_contains = [str(token).strip() for token in (context.get("required_comment_contains") or []) if str(token).strip()]
        if required_action_tools or required_statuses:
            contract_lines = []
            if required_action_tools:
                contract_lines.append(f"- Required tool calls this turn: {', '.join(required_action_tools)}")
                if not bool(context.get("protocol_governed_enabled", False)):
                    contract_lines.append(
                        '- Return exactly one JSON object: {"content":"","tool_calls":[...]}'
                    )
                    contract_lines.append(
                        "- Put every required tool call into tool_calls within that single JSON object."
                    )
                    contract_lines.append(
                        "- Do not use markdown fences, labels, or multiple top-level JSON objects."
                    )
            if required_statuses:
                contract_lines.append(f"- Required update_issue_status.status values: {', '.join(required_statuses)}")
                if "blocked" in required_statuses:
                    contract_lines.append(
                        "- If you choose status=blocked, include wait_reason: resource|dependency|review|input|system."
                    )
            contract_lines.append("- You must include all required tool calls in this same response.")
            contract_lines.append("- A response containing only get_issue_context/add_issue_comment is invalid.")
            if write_path_contract_required:
                contract_lines.append("- Empty or placeholder content for required write_file paths is invalid.")
                contract_lines.append(
                    "- When writing Python source through write_file, prefer single-quoted literals to keep the JSON payload valid."
                )
            messages.append({"role": "user", "content": "Turn Success Contract:\n" + "\n".join(contract_lines)})

        if required_write_paths and write_path_contract_required:
            write_lines = [
                "- Required write_file paths this turn:",
                *[f"  - {path}" for path in required_write_paths],
                "- Use workspace-relative paths exactly as listed.",
            ]
            messages.append({"role": "user", "content": "Write Path Contract:\n" + "\n".join(write_lines)})

        should_preload_read_context = bool(required_read_paths) and (
            read_path_contract_required
            or "add_issue_comment" in required_action_tools
            or required_comment_min_length
            or required_comment_contains
            or profile_intent in {"write_artifact", "build_app"}
        )
        if required_read_paths and read_path_contract_required:
            read_lines = [
                "- Required read_file paths this turn:",
                *[f"  - {path}" for path in required_read_paths],
                "- Do not use placeholder or absolute paths outside the workspace.",
            ]
            messages.append({"role": "user", "content": "Read Path Contract:\n" + "\n".join(read_lines)})
        if should_preload_read_context:
            preloaded_read_context = await self._load_required_read_context(required_read_paths)
            if preloaded_read_context:
                messages.append(
                    {
                        "role": "user",
                        "content": "Preloaded Read Context:\n" + "\n\n".join(preloaded_read_context),
                    }
                )

        prompt_required_comment_contains = list(required_comment_contains)
        for path_token in required_read_paths:
            if path_token and path_token not in prompt_required_comment_contains:
                prompt_required_comment_contains.append(path_token)
        if "add_issue_comment" in required_action_tools or required_comment_min_length or required_comment_contains:
            comment_lines = [
                "- Required add_issue_comment payloads must be concrete and evidence-linked.",
                "- Ground comment claims in the preloaded read context or files explicitly listed in the Read Path Contract.",
                "- Cite every required read path by exact path string when a Read Path Contract is present.",
                '- Quote short inline snippets only, for example "Truthful failure detection".',
                "- Do not use markdown fences or multi-line code blocks inside comment strings.",
            ]
            if required_read_paths:
                comment_lines.append(
                    "- Exact required path tokens to cite: " + ", ".join(required_read_paths)
                )
                comment_lines.append(
                    "- A simple compliant citation pattern is: (" + ", ".join(required_read_paths) + ")."
                )
            if required_comment_min_length:
                comment_lines.append(
                    f"- At least one add_issue_comment.comment value must be at least {int(required_comment_min_length)} characters."
                )
            if prompt_required_comment_contains:
                comment_lines.append(
                    "- At least one add_issue_comment.comment value must contain: "
                    + ", ".join(prompt_required_comment_contains)
                )
            messages.append({"role": "user", "content": "Comment Contract:\n" + "\n".join(comment_lines)})

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

        if bool(context.get("compact_turn_packet_enabled", True)):
            compaction = compact_turn_messages(messages, runtime_context=context)
            messages = compaction.messages
            if compaction.applied:
                prompt_metadata = context.get("prompt_metadata")
                if isinstance(prompt_metadata, dict):
                    prompt_metadata["prompt_checksum"] = hashlib.sha256(
                        str(messages[0].get("content") or "").encode("utf-8")
                    ).hexdigest()[:16]
                    prompt_metadata["prompt_packet_version"] = compaction.packet_version
                    prompt_metadata["prompt_packet_compacted"] = True
                prompt_layers = context.get("prompt_layers")
                if isinstance(prompt_layers, dict):
                    prompt_layers["packet_compaction"] = {
                        "enabled": True,
                        "version": compaction.packet_version,
                        "source_message_count": compaction.source_message_count,
                        "compacted_message_count": compaction.compacted_message_count,
                    }

        return messages

    async def _load_required_read_context(self, required_read_paths: list[str]) -> list[str]:
        rendered: list[str] = []
        for rel_path in required_read_paths:
            candidate = (self.workspace / rel_path).resolve()
            if not candidate.exists() or not candidate.is_file():
                continue
            async with aiofiles.open(candidate, mode="r", encoding="utf-8") as handle:
                content = await handle.read()
            normalized = content.replace("\r\n", "\n")
            truncated = False
            if len(normalized) > _MAX_PRELOADED_READ_CONTEXT_CHARS:
                normalized = normalized[:_MAX_PRELOADED_READ_CONTEXT_CHARS]
                truncated = True
            block = f"Path: {rel_path}\nContent:\n{normalized}"
            if truncated:
                block += "\n[truncated]"
            rendered.append(block)
        return rendered
