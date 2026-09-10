from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Literal, cast

from orket.core.contracts import CheckpointRecord, EffectJournalEntryRecord
from orket.core.domain import CheckpointResumabilityClass
from orket_extension_sdk import (
    AgentEffectProposal,
    AgentEffectReceipt,
    AgentIterationRequest,
    AgentIterationResult,
    canonical_digest_sha256,
)


def proposal_arguments(proposal: AgentEffectProposal) -> tuple[str, dict[str, Any]]:
    if not proposal.namespace.startswith("issue:"):
        raise ValueError("E_AGENT_EFFECT_ISSUE_NAMESPACE_REQUIRED")
    arguments = proposal.arguments.thaw() if proposal.arguments is not None else None
    if not isinstance(arguments, dict) or arguments.get("path") != proposal.intended_target:
        raise ValueError("E_AGENT_EFFECT_ARGUMENTS_INVALID")
    if proposal.capability == "write_file" and not isinstance(arguments.get("content"), (str, dict)):
        raise ValueError("E_AGENT_EFFECT_WRITE_CONTENT_INVALID")
    return proposal.namespace.removeprefix("issue:"), arguments


def content_matches(observed: Any, intended: Any) -> bool:
    if isinstance(intended, dict) and isinstance(observed, str):
        try:
            return bool(json.loads(observed) == intended)
        except json.JSONDecodeError:
            return False
    return bool(observed == intended)


def approval_id(proposal: AgentEffectProposal) -> str:
    digest = cast(str, canonical_digest_sha256(proposal.to_wire()))
    return f"agent-effect-{digest[:32]}"


def approval_payload(approval: Mapping[str, Any]) -> dict[str, Any]:
    payload = approval.get("payload_json") or approval.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("E_AGENT_EFFECT_APPROVAL_PAYLOAD_INVALID")
    return payload


def approval_view(approval: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **approval,
        "approval_id": approval.get("request_id"),
        "payload": approval_payload(approval),
        "resolution": approval.get("resolution_json") or {},
    }


def effect_receipt(
    proposal: AgentEffectProposal,
    state: Literal["proposed", "approved", "denied", "executed", "observed", "uncertain", "reconciled"],
    authority_ref: str,
    observations: tuple[str, ...],
) -> AgentEffectReceipt:
    return AgentEffectReceipt(
        receipt_id=f"agent-effect-receipt:{proposal.proposal_id}:{state}",
        proposal_id=proposal.proposal_id,
        identity=proposal.identity,
        capability=proposal.capability,
        intended_target=proposal.intended_target,
        arguments_digest=proposal.arguments_digest,
        state=state,
        authority_ref=authority_ref,
        observation_refs=tuple(item for item in observations if item),
    )


def pre_effect_checkpoint(
    request: Any,
    proposal: AgentEffectProposal,
    timestamp: str,
) -> CheckpointRecord:
    return CheckpointRecord(
        checkpoint_id=f"agent-pre-effect-checkpoint:{proposal.proposal_id}",
        parent_ref=proposal.identity.attempt_id,
        creation_timestamp=timestamp,
        state_snapshot_ref=f"agent-result:{proposal.identity.invocation_id}",
        resumability_class=CheckpointResumabilityClass.RESUME_FORBIDDEN,
        invalidation_conditions=["effect_resolution_missing", "effect_boundary_uncertain"],
        dependent_effect_refs=[f"agent-effect:{proposal.proposal_id}"],
        policy_digest=request.policy_digest,
        integrity_verification_ref=proposal.arguments_digest,
    )


def post_effect_checkpoint(
    proposal: AgentEffectProposal,
    journal: Any,
    timestamp: str,
    policy_digest: str,
) -> CheckpointRecord:
    return CheckpointRecord(
        checkpoint_id=f"agent-post-effect-checkpoint:{proposal.proposal_id}",
        parent_ref=proposal.identity.attempt_id,
        creation_timestamp=timestamp,
        state_snapshot_ref=str(journal.observed_result_ref),
        resumability_class=CheckpointResumabilityClass.RESUME_SAME_ATTEMPT,
        invalidation_conditions=["effect_observation_drift", "policy_digest_drift"],
        dependent_effect_refs=[journal.effect_id],
        policy_digest=policy_digest,
        integrity_verification_ref=journal.entry_digest,
    )


def aggregate_effect_checkpoint(
    request: AgentIterationRequest,
    result: AgentIterationResult,
    journal_entries: tuple[EffectJournalEntryRecord, ...],
    timestamp: str,
) -> CheckpointRecord:
    proposal_ids = {proposal.proposal_id for proposal in result.effect_proposals}
    entries = tuple(
        sorted(
            (entry for entry in journal_entries if entry.effect_id.removeprefix("agent-effect:") in proposal_ids),
            key=lambda entry: entry.effect_id,
        )
    )
    if len(entries) != len(proposal_ids):
        raise ValueError("E_AGENT_EFFECT_CHECKPOINT_COVERAGE_INCOMPLETE")
    integrity_payload = {
        "accepted_result_digest": "sha256:" + canonical_digest_sha256(result.to_wire()),
        "proposals": [
            {"proposal_id": proposal.proposal_id, "arguments_digest": proposal.arguments_digest}
            for proposal in sorted(result.effect_proposals, key=lambda item: item.proposal_id)
        ],
        "journals": [
            {"journal_entry_id": entry.journal_entry_id, "entry_digest": entry.entry_digest}
            for entry in entries
        ],
    }
    integrity_ref = "sha256:" + cast(str, canonical_digest_sha256(integrity_payload))
    return CheckpointRecord(
        checkpoint_id=f"agent-post-effects-checkpoint:{request.identity.invocation_id}",
        parent_ref=request.identity.attempt_id,
        creation_timestamp=timestamp,
        state_snapshot_ref=integrity_ref,
        resumability_class=CheckpointResumabilityClass.RESUME_SAME_ATTEMPT,
        invalidation_conditions=["effect_observation_drift", "policy_digest_drift"],
        dependent_effect_refs=[entry.effect_id for entry in entries],
        policy_digest=request.policy_digest,
        integrity_verification_ref=integrity_ref,
    )


__all__ = [
    "aggregate_effect_checkpoint",
    "approval_id",
    "approval_payload",
    "approval_view",
    "content_matches",
    "effect_receipt",
    "post_effect_checkpoint",
    "pre_effect_checkpoint",
    "proposal_arguments",
]
