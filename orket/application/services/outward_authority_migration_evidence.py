"""Validate retained outward history before explicit current-input adoption."""

from __future__ import annotations

import json
from dataclasses import replace

from orket.application.services.outward_authorization_service import resolved_policy
from orket.application.services.outward_effect_authority import validate_effect_authority
from orket.application.services.outward_model_admission_inputs import validate_admission_inputs
from orket.application.services.outward_model_recovery_records import validate_model_attempt_history
from orket.application.services.outward_run_execution_plan import current_step_index
from orket.application.services.outward_run_lifecycle import terminal_projection
from orket.application.services.outward_terminal_evidence import terminal_evidence_refs


async def migration_evidence(transaction, snapshot):
    run, events = snapshot.run, snapshot.events
    initial = next((event for event in events if event.event_id == f"run:{run.run_id}:submitted"), None)
    if (initial is None or initial.event_type != "run_submitted" or initial.at != run.submitted_at
            or initial.payload.get("namespace") != run.namespace
            or initial.payload.get("policy_overrides") != run.policy_overrides):
        raise RuntimeError("E_OUTWARD_MIGRATION_ADMISSION_CONFLICT")
    proposals = await _validate_proposals(transaction, run, events)
    terminal = [event for event in events if event.event_type in {"run_completed", "run_failed"}]
    if run.status in {"queued", "running", "approval_required"}:
        if terminal or run.completed_at is not None:
            raise RuntimeError("E_OUTWARD_MIGRATION_TERMINAL_CONFLICT")
        queued = [proposal.to_queue_payload() for proposal in proposals if proposal.status == "pending"]
        if list(run.pending_proposals) != queued:
            raise RuntimeError("E_OUTWARD_MIGRATION_PENDING_CONFLICT")
        attempts = await transaction.models.list_attempts(run.run_id, run.execution_generation, run.current_turn, current_step_index(run))
        await validate_model_attempt_history(transaction, attempts)
        if attempts and attempts[-1].state != "published":
            validate_admission_inputs(attempts[-1], run)
        return None
    if run.status not in {"completed", "failed"} or len(terminal) > 1 or run.completed_at is None:
        raise RuntimeError("E_OUTWARD_MIGRATION_TERMINAL_CONFLICT")
    outcome, cause = await _terminal_cause(transaction, run, events, proposals, terminal)
    if terminal_projection(outcome)[0] != run.status:
        raise RuntimeError("E_OUTWARD_MIGRATION_TERMINAL_CONFLICT")
    await terminal_evidence_refs(transaction, run, outcome=outcome, cause=cause)
    return outcome, cause


async def _validate_proposals(transaction, run, events):
    pending = [event for event in events if event.event_type == "proposal_pending_approval"]
    ids = [event.payload.get("proposal_id") for event in pending]
    if len(set(ids)) != len(ids) or await transaction.count_proposals(run.run_id) != len(ids):
        raise RuntimeError("E_OUTWARD_MIGRATION_PROPOSAL_HISTORY_CONFLICT")
    proposals = []
    for event in pending:
        proposal = await transaction.get_proposal(event.payload["proposal_id"])
        if proposal is None or replace(proposal, status="pending").to_queue_payload() != event.payload:
            raise RuntimeError("E_OUTWARD_MIGRATION_PROPOSAL_HISTORY_CONFLICT")
        binding = proposal.authorization
        if (binding is None or (binding.run_id, binding.execution_generation, binding.namespace)
                != (run.run_id, run.execution_generation, run.namespace)
                or resolved_policy(run, json.loads(binding.policy_json)["connector_policy"]) != binding.policy_json):
            raise RuntimeError("E_OUTWARD_MIGRATION_AUTHORIZATION_CONFLICT")
        effect = await transaction.effects.get(binding.effect_id)
        if effect is not None:
            if proposal.status != "approved":
                raise RuntimeError("E_OUTWARD_MIGRATION_EFFECT_WITHOUT_APPROVAL")
            await validate_effect_authority(transaction, binding, effect)
        proposals.append(proposal)
    return proposals


async def _terminal_cause(transaction, run, events, proposals, terminal):
    outcome = terminal[0].payload.get("outcome") if terminal else None
    if outcome == "success":
        return outcome, terminal[0]
    for candidate in reversed(proposals):
        if candidate.status in {"denied", "expired"}:
            if outcome is not None and outcome != candidate.status:
                raise RuntimeError("E_OUTWARD_MIGRATION_TERMINAL_CONFLICT")
            return candidate.status, candidate
    for event in reversed(events):
        if event.event_type in {"proposal_policy_rejected", "trust_handoff_rejected"}:
            expected = "policy_rejected" if event.event_type == "proposal_policy_rejected" else "handoff_rejected"
            if outcome != expected:
                raise RuntimeError("E_OUTWARD_MIGRATION_TERMINAL_CONFLICT")
            return expected, event
    if run.status == "failed":
        model = await transaction.models.get(run.run_id, run.execution_generation, run.current_turn, current_step_index(run))
        if model is not None and model.state in {"observed", "published"} and "error" in model.result:
            return "failed", model
        if proposals:
            effect = await transaction.effects.get(proposals[-1].authorization.effect_id)
            if effect is not None and effect.state in {"observed", "published"}:
                return "failed", effect
    raise RuntimeError("E_OUTWARD_MIGRATION_TERMINAL_EVIDENCE_MISSING")
