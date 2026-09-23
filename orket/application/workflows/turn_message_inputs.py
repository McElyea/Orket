from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.schema import IssueConfig, RoleConfig

_PROMPT_CONTEXT_KEYS = (
    "role", "current_status", "runtime_retry_note", "issue_id", "dependency_context",
    "execution_profile", "base_execution_profile", "builder_seat_choice", "reviewer_seat_choice",
    "profile_traits", "seat_coercion", "artifact_contract", "scenario_truth", "odr_active",
    "required_action_tools", "required_statuses", "required_read_paths", "required_write_paths",
    "required_comment_min_length", "required_comment_contains", "stage_gate_mode", "runtime_verifier_ok",
    "runtime_verifier_enabled", "runtime_verifier_contract", "architecture_mode", "frontend_framework_mode",
    "architecture_decision_required", "architecture_decision_path", "architecture_forced_pattern",
    "architecture_allowed_patterns", "frontend_framework_allowed", "frontend_framework_forced",
    "protocol_governed_enabled", "session_id", "turn_index", "odr_valid", "odr_pending_decisions",
    "odr_stop_reason", "odr_termination_reason", "odr_final_auditor_verdict", "odr_artifact_path",
    "odr_requirement", "verification_scope", "history", "compact_turn_packet_enabled", "prompt_metadata",
    "card_completion_decision", "card_completion_context",
)

_FROZEN_CARD_CONTEXT_KEYS = ("card_completion_decision", "card_completion_context")


@dataclass(frozen=True)
class TurnMessageInputs:
    workspace: Path
    issue: IssueConfig
    role: RoleConfig
    context: dict[str, Any]
    system_prompt: str | None
    prompt_metadata_sink: dict[str, Any] | None
    prompt_layers_sink: dict[str, Any] | None


def capture_turn_message_inputs(
    *, workspace: Path, issue: IssueConfig, role: RoleConfig, context: dict[str, Any], system_prompt: str | None,
) -> TurnMessageInputs:
    """Detach prompt inputs without traversing unrelated runtime resources."""
    captured_workspace, = capture_file_roots([workspace])
    captured_issue = issue.model_copy(update={"references": list(issue.references)})
    captured_role = role.model_copy(update={"tools": list(role.tools)})
    prompt_metadata_sink = context.get("prompt_metadata")
    prompt_layers_sink = context.get("prompt_layers")
    copied_values = {
        key: context[key]
        for key in _PROMPT_CONTEXT_KEYS
        if key in context and key not in _FROZEN_CARD_CONTEXT_KEYS
    }
    captured_context = deepcopy(copied_values)
    captured_context.update({key: context[key] for key in _FROZEN_CARD_CONTEXT_KEYS if key in context})
    return TurnMessageInputs(
        workspace=captured_workspace,
        issue=captured_issue,
        role=captured_role,
        context=captured_context,
        system_prompt=system_prompt,
        prompt_metadata_sink=prompt_metadata_sink if isinstance(prompt_metadata_sink, dict) else None,
        prompt_layers_sink=prompt_layers_sink if isinstance(prompt_layers_sink, dict) else None,
    )


def publish_compaction_outputs(
    *, inputs: TurnMessageInputs, messages: list[dict[str, str]], compaction: Any,
) -> None:
    if inputs.prompt_metadata_sink is not None:
        inputs.prompt_metadata_sink["prompt_checksum"] = hashlib.sha256(
            str(messages[0].get("content") or "").encode("utf-8")
        ).hexdigest()[:16]
        inputs.prompt_metadata_sink["prompt_packet_version"] = compaction.packet_version
        inputs.prompt_metadata_sink["prompt_packet_compacted"] = True
    if inputs.prompt_layers_sink is not None:
        inputs.prompt_layers_sink["packet_compaction"] = {
            "enabled": True,
            "version": compaction.packet_version,
            "source_message_count": compaction.source_message_count,
            "compacted_message_count": compaction.compacted_message_count,
        }
