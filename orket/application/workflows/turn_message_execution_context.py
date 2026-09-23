"""Build the prompt execution-context projection from captured named values."""
from __future__ import annotations

from typing import Any

from orket.application.services.card_completion_prompt import card_completion_prompt_payload

from .turn_artifact_destination import TurnArtifactDestination


def build_message_execution_context(
    *, destination: TurnArtifactDestination, context: dict[str, Any],
    required_read_paths: list[str], missing_required_read_paths: list[str],
) -> dict[str, Any]:
    return {
        "issue_id": destination.issue_id,
        "seat": destination.role_name,
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
        "runtime_verifier_enabled": context.get("runtime_verifier_enabled", True),
        "card_completion": card_completion_prompt_payload(context),
        "architecture_mode": context.get("architecture_mode"),
        "frontend_framework_mode": context.get("frontend_framework_mode"),
        "architecture_decision_required": bool(context.get("architecture_decision_required")),
        "architecture_decision_path": context.get("architecture_decision_path"),
        "architecture_forced_pattern": context.get("architecture_forced_pattern"),
        "frontend_framework_forced": context.get("frontend_framework_forced"),
        "prompt_metadata": context.get("prompt_metadata", {}),
    }
