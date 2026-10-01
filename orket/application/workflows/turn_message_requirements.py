"""Keep required-path formatting, read observation and missing-input publication ordered."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .turn_artifact_destination import TurnArtifactDestination
from .turn_read_context import preload_required_read_context, publish_missing_read_event


@dataclass(frozen=True)
class MessageRequirements:
    required_action_tools: list[str]
    required_statuses: list[str]
    read_path_contract_required: bool
    required_comment_min_length: Any
    required_comment_contains: list[str]
    should_preload_read_context: object


def prepare_turn_requirements(
    messages: list[dict[str, str]],
    context: dict[str, Any],
    required_write_paths: list[str],
    required_read_paths: list[str],
) -> MessageRequirements:
    required_action_tools = [str(t) for t in context.get("required_action_tools") or [] if t]
    if "read_file" in required_action_tools and (not required_read_paths):
        required_action_tools = [tool for tool in required_action_tools if tool != "read_file"]
    read_path_contract_required = "read_file" in required_action_tools
    write_path_contract_required = "write_file" in required_action_tools
    profile_intent = (
        str(
            (context.get("profile_traits") or {} if isinstance(context.get("profile_traits"), dict) else {}).get(
                "intent"
            )
            or ""
        )
        .strip()
        .lower()
    )
    required_statuses = [str(s).strip().lower() for s in context.get("required_statuses") or [] if s]
    required_comment_min_length = context.get("required_comment_min_length")
    required_comment_contains = [
        str(token).strip() for token in context.get("required_comment_contains") or [] if str(token).strip()
    ]
    append_success_contract(messages, context, required_action_tools, required_statuses, write_path_contract_required)
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
        or (profile_intent in {"write_artifact", "build_app"})
    )
    return MessageRequirements(
        required_action_tools,
        required_statuses,
        read_path_contract_required,
        required_comment_min_length,
        required_comment_contains,
        should_preload_read_context,
    )


def append_success_contract(
    messages: list[dict[str, str]],
    context: dict[str, Any],
    required_action_tools: list[str],
    required_statuses: list[str],
    write_path_contract_required: bool,
) -> None:
    if required_action_tools or required_statuses:
        contract_lines = []
        if required_action_tools:
            contract_lines.append(f"- Required tool calls this turn: {', '.join(required_action_tools)}")
            if not bool(context.get("protocol_governed_enabled", False)):
                contract_lines.append('- Return exactly one JSON object: {"content":"","tool_calls":[...]}')
                contract_lines.append("- Put every required tool call into tool_calls within that single JSON object.")
                contract_lines.append("- Do not use markdown fences, labels, or multiple top-level JSON objects.")
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


async def append_read_context(
    messages: list[dict[str, str]], required_read_paths: list[str], workspace: Path, requirements: MessageRequirements
) -> None:
    if required_read_paths and requirements.read_path_contract_required:
        read_lines = [
            "- Required read_file paths this turn:",
            *[f"  - {path}" for path in required_read_paths],
            "- Do not use placeholder or absolute paths outside the workspace.",
        ]
        messages.append({"role": "user", "content": "Read Path Contract:\n" + "\n".join(read_lines)})
    if requirements.should_preload_read_context:
        preloaded_read_context = await preload_required_read_context(
            required_read_paths=required_read_paths, workspace=workspace
        )
        if preloaded_read_context:
            messages.append(
                {"role": "user", "content": "Preloaded Read Context:\n" + "\n\n".join(preloaded_read_context)}
            )


def append_comment_contract(
    messages: list[dict[str, str]], required_read_paths: list[str], requirements: MessageRequirements
) -> None:
    prompt_required_comment_contains = list(requirements.required_comment_contains)
    for path_token in required_read_paths:
        if path_token and path_token not in prompt_required_comment_contains:
            prompt_required_comment_contains.append(path_token)
    if (
        "add_issue_comment" in requirements.required_action_tools
        or requirements.required_comment_min_length
        or requirements.required_comment_contains
    ):
        comment_lines = [
            "- Required add_issue_comment payloads must be concrete and evidence-linked.",
            "- Ground comment claims in the preloaded read context or files explicitly listed in the Read Path Contract.",
            "- Cite every required read path by exact path string when a Read Path Contract is present.",
            '- Quote short inline snippets only, for example "Truthful failure detection".',
            "- Do not use markdown fences or multi-line code blocks inside comment strings.",
        ]
        if required_read_paths:
            comment_lines.append("- Exact required path tokens to cite: " + ", ".join(required_read_paths))
            comment_lines.append("- A simple compliant citation pattern is: (" + ", ".join(required_read_paths) + ").")
        if requirements.required_comment_min_length:
            comment_lines.append(
                f"- At least one add_issue_comment.comment value must be at least {int(requirements.required_comment_min_length)} characters."
            )
        if prompt_required_comment_contains:
            comment_lines.append(
                "- At least one add_issue_comment.comment value must contain: "
                + ", ".join(prompt_required_comment_contains)
            )
        messages.append({"role": "user", "content": "Comment Contract:\n" + "\n".join(comment_lines)})


async def append_missing_read_notice(
    messages: list[dict[str, str]],
    context: dict[str, Any],
    missing_required_read_paths: list[str],
    workspace: Path,
    destination: TurnArtifactDestination,
    requirements: MessageRequirements,
) -> None:
    should_emit_missing_read_notice = bool(missing_required_read_paths) and requirements.read_path_contract_required
    if should_emit_missing_read_notice:
        await publish_missing_read_event(
            issue_id=destination.issue_id,
            role_name=destination.role_name,
            session_id=context.get("session_id", "unknown-session"),
            turn_index=context.get("turn_index", 0),
            missing_required_read_paths=missing_required_read_paths,
            workspace=workspace,
        )
        missing_lines = [
            "- The following expected read paths are currently missing in workspace:",
            *[f"  - {path}" for path in missing_required_read_paths],
            "- Do not fabricate reads for missing paths; proceed with available files and state missing inputs explicitly.",
        ]
        messages.append({"role": "user", "content": "Missing Input Preflight Notice:\n" + "\n".join(missing_lines)})
