from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.runtime.compact_turn_packet import compact_turn_messages
from orket.schema import IssueConfig, RoleConfig

from .turn_artifact_destination import TurnArtifactDestination
from .turn_message_contracts import append_artifact_contract, append_scenario_contract, append_verifier_contract
from .turn_message_inputs import capture_turn_message_inputs, publish_compaction_outputs
from .turn_message_requirements import (
    append_comment_contract,
    append_missing_read_notice,
    append_read_context,
    prepare_turn_requirements,
)
from .turn_message_sections import (
    append_architecture_contract,
    append_protocol_context,
    append_review_and_history,
    append_verification_scope,
    initial_messages,
)
from .turn_read_context import observe_required_read_paths


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
        destination: TurnArtifactDestination,
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        inputs = capture_turn_message_inputs(
            workspace=destination.workspace, issue=issue, role=role, context=context, system_prompt=system_prompt
        )
        workspace, issue, role = (inputs.workspace, inputs.issue, inputs.role)
        context, system_prompt = (inputs.context, inputs.system_prompt)
        context.update(
            session_id=destination.session_id,
            issue_id=destination.issue_id,
            role=destination.role_name,
            turn_index=destination.turn_index,
        )
        read_observation = await observe_required_read_paths(context=context, workspace=workspace)
        required_read_paths = list(read_observation.existing)
        missing_required_read_paths = list(read_observation.missing)
        messages, issue_brief_message, required_write_paths = initial_messages(
            issue, role, context, destination, system_prompt, required_read_paths, missing_required_read_paths
        )
        artifact_contract = context.get("artifact_contract")
        append_artifact_contract(messages, context, artifact_contract)
        append_scenario_contract(messages, context, destination)
        append_verifier_contract(messages, context, artifact_contract)
        if issue_brief_message is not None:
            messages.append(issue_brief_message)
        append_protocol_context(messages, context)
        requirements = prepare_turn_requirements(messages, context, required_write_paths, required_read_paths)
        await append_read_context(messages, required_read_paths, workspace, requirements)
        append_comment_contract(messages, required_read_paths, requirements)
        await append_missing_read_notice(
            messages, context, missing_required_read_paths, workspace, destination, requirements
        )
        append_verification_scope(messages, context)
        append_architecture_contract(messages, context)
        append_review_and_history(messages, context, requirements.required_statuses)
        if bool(context.get("compact_turn_packet_enabled", True)):
            compaction = compact_turn_messages(messages, runtime_context={**context, "available_tools": role.tools})
            messages = compaction.messages
            if compaction.applied:
                publish_compaction_outputs(inputs=inputs, messages=messages, compaction=compaction)
        return messages
