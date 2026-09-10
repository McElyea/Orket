from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.governed_agent_context_plan import retained_continuation_inputs
from orket.application.services.governed_agent_effect_control_support import (
    _optional_text,
    _require_run_approval,
    _required_text,
    _resume_timings,
    _string_sequence,
    _utc_timestamp,
)
from orket.application.services.governed_agent_effect_records import (
    aggregate_effect_checkpoint,
    effect_receipt,
)
from orket.application.services.governed_agent_effect_resume_service import (
    RESUMABLE_AGENT_RULES,
    GovernedAgentEffectResumeService,
)
from orket.application.services.governed_agent_effect_service import (
    GovernedAgentEffectResolution,
    GovernedAgentEffectService,
)
from orket.application.services.governed_agent_iteration_policy import agent_payload_digest
from orket.application.services.governed_agent_ports import GovernedAgentIterationRepository
from orket.application.services.governed_agent_wake_ingress_service import (
    GovernedAgentWakeSubmission,
    notify_wake_ready,
)
from orket.application.services.governed_agent_wake_records import (
    GovernedAgentWakeEnqueueResult,
    GovernedAgentWakeRepository,
)
from orket.core.contracts import EffectJournalEntryRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import CheckpointReobservationClass, ResidualUncertaintyClassification, RunState
from orket_extension_sdk import AgentEffectReceipt, AgentIterationRequest, AgentIterationResult

EffectControlStatus = Literal["denied", "awaiting_effects", "recovery_required", "resume_queued"]


@dataclass(frozen=True, slots=True)
class GovernedAgentEffectControlResult:
    status: EffectControlStatus
    resolution: GovernedAgentEffectResolution | None
    accepted_checkpoint_ref: str | None
    resume_operator_action_ref: str | None
    wake: GovernedAgentWakeEnqueueResult | None


class GovernedAgentEffectControlService:
    """Resolve one agent effect and enqueue only a fully authorized resume."""

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        iteration_repository: GovernedAgentIterationRepository,
        publication: ControlPlanePublicationService,
        effects: GovernedAgentEffectService,
        resumes: GovernedAgentEffectResumeService,
        wakes: GovernedAgentWakeRepository,
        notify_ready: Callable[[], None] | None = None,
    ) -> None:
        self._execution = execution_repository
        self._iterations = iteration_repository
        self._publication = publication
        self._effects = effects
        self._resumes = resumes
        self._wakes = wakes
        self._notify_ready = notify_ready

    async def apply(
        self,
        *,
        run_id: str,
        approval_id_ref: str | None,
        payload: Mapping[str, object],
    ) -> GovernedAgentEffectControlResult:
        allowed = {
            "decision",
            "actor_ref",
            "timestamp_utc",
            "next_lease_expires_at_utc",
            "decision_timestamps_utc",
            "next_lease_expiries_utc",
        }
        if set(payload) - allowed:
            raise ValueError("E_AGENT_EFFECT_CONTROL_FIELD_UNKNOWN")
        actor = _required_text(payload.get("actor_ref"), "E_AGENT_EFFECT_ACTOR_REQUIRED")
        timestamp = _required_text(payload.get("timestamp_utc"), "E_AGENT_EFFECT_TIMESTAMP_REQUIRED")
        lease = _optional_text(payload.get("next_lease_expires_at_utc"))
        decisions = _string_sequence(payload.get("decision_timestamps_utc"))
        expiries = _string_sequence(payload.get("next_lease_expiries_utc"))
        if approval_id_ref is None:
            if "decision" in payload:
                raise ValueError("E_AGENT_EFFECT_RESUME_DECISION_UNEXPECTED")
            return await self.resume(
                run_id=run_id,
                actor_ref=actor,
                timestamp_utc=timestamp,
                next_lease_expires_at_utc=lease,
                decision_timestamps_utc=decisions,
                next_lease_expiries_utc=expiries,
            )
        return await self.resolve(
            run_id=run_id,
            approval_id_ref=approval_id_ref,
            decision=str(payload.get("decision") or ""),
            actor_ref=actor,
            timestamp_utc=timestamp,
            next_lease_expires_at_utc=lease,
            decision_timestamps_utc=decisions,
            next_lease_expiries_utc=expiries,
        )

    async def resolve(
        self,
        *,
        run_id: str,
        approval_id_ref: str,
        decision: str,
        actor_ref: str,
        timestamp_utc: str,
        next_lease_expires_at_utc: str | None,
        decision_timestamps_utc: Sequence[str],
        next_lease_expiries_utc: Sequence[str],
    ) -> GovernedAgentEffectControlResult:
        request, result = await self._effect_context(run_id)
        normalized_decision = str(decision).strip().lower()
        timestamp = _utc_timestamp(timestamp_utc)
        decision_timestamps, lease_expiries = _resume_timings(
            request=request,
            decision=normalized_decision,
            next_lease_expires_at_utc=next_lease_expires_at_utc,
            decision_timestamps_utc=decision_timestamps_utc,
            next_lease_expiries_utc=next_lease_expiries_utc,
        )
        _require_run_approval(result, approval_id_ref)
        resolution = await self._effects.resolve_write(
            approval_id=approval_id_ref,
            decision=normalized_decision,
            actor_ref=actor_ref,
            timestamp=timestamp,
        )
        if resolution.receipt.state == "denied":
            return GovernedAgentEffectControlResult("denied", resolution, None, None, None)
        receipts, journals = await self._safe_receipts(result)
        if receipts is None:
            status = await self._awaiting_status(run_id)
            return GovernedAgentEffectControlResult(status, resolution, None, None, None)
        return await self._queue_resume(
            request=request,
            result=result,
            receipts=receipts,
            journals=journals,
            resolution=resolution,
            actor_ref=actor_ref,
            timestamp=timestamp,
            next_lease_expires_at_utc=str(next_lease_expires_at_utc),
            decision_timestamps_utc=decision_timestamps,
            next_lease_expiries_utc=lease_expiries,
        )

    async def resume(
        self,
        *,
        run_id: str,
        actor_ref: str,
        timestamp_utc: str,
        next_lease_expires_at_utc: str | None,
        decision_timestamps_utc: Sequence[str],
        next_lease_expiries_utc: Sequence[str],
    ) -> GovernedAgentEffectControlResult:
        request, result = await self._effect_context(run_id)
        timestamp = _utc_timestamp(timestamp_utc)
        decision_timestamps, lease_expiries = _resume_timings(
            request=request,
            decision="approved",
            next_lease_expires_at_utc=next_lease_expires_at_utc,
            decision_timestamps_utc=decision_timestamps_utc,
            next_lease_expiries_utc=next_lease_expiries_utc,
        )
        receipts, journals = await self._safe_receipts(result)
        if receipts is None:
            return GovernedAgentEffectControlResult(
                await self._awaiting_status(run_id), None, None, None, None
            )
        return await self._queue_resume(
            request=request,
            result=result,
            receipts=receipts,
            journals=journals,
            resolution=None,
            actor_ref=actor_ref,
            timestamp=timestamp,
            next_lease_expires_at_utc=str(next_lease_expires_at_utc),
            decision_timestamps_utc=decision_timestamps,
            next_lease_expiries_utc=lease_expiries,
        )

    async def _queue_resume(
        self,
        *,
        request: AgentIterationRequest,
        result: AgentIterationResult,
        receipts: tuple[AgentEffectReceipt, ...],
        journals: tuple[EffectJournalEntryRecord, ...],
        resolution: GovernedAgentEffectResolution | None,
        actor_ref: str,
        timestamp: str,
        next_lease_expires_at_utc: str,
        decision_timestamps_utc: Sequence[str],
        next_lease_expiries_utc: Sequence[str],
    ) -> GovernedAgentEffectControlResult:
        checkpoint = aggregate_effect_checkpoint(request, result, journals, timestamp)
        acceptance = await self._publication.accept_checkpoint(
            acceptance_id=f"agent-effects-checkpoint-acceptance:{request.identity.invocation_id}",
            checkpoint=checkpoint,
            supervisor_authority_ref="governed-agent-effect-control-service:v1",
            decision_timestamp=timestamp,
            required_reobservation_class=CheckpointReobservationClass.NONE,
            integrity_verification_ref=checkpoint.integrity_verification_ref,
            journal_entries=journals,
            dependent_effect_entry_refs=tuple(entry.journal_entry_id for entry in journals),
        )
        context_plan = await retained_continuation_inputs(self._wakes, request.identity.run_id)
        resume = await self._resumes.prepare_resume(
            run_id=request.identity.run_id,
            effect_receipts=receipts,
            accepted_checkpoint_ref=acceptance.checkpoint_id,
            next_lease_expires_at_utc=next_lease_expires_at_utc,
            actor_ref=actor_ref,
            timestamp=timestamp,
            next_context_inputs=context_plan.get(str(request.identity.iteration_ordinal + 1)),
        )
        wake = await self._enqueue_resume(
            request=resume.request,
            run_creation_timestamp_utc=await self._run_creation_timestamp(request.identity.run_id),
            decision_timestamps_utc=decision_timestamps_utc,
            next_lease_expiries_utc=next_lease_expiries_utc,
            created_at_utc=timestamp,
            continuation_inputs=context_plan,
        )
        return GovernedAgentEffectControlResult(
            "resume_queued",
            resolution,
            acceptance.checkpoint_id,
            resume.operator_action_ref,
            wake,
        )

    async def _awaiting_status(self, run_id: str) -> EffectControlStatus:
        run = await self._execution.get_run_record(run_id=run_id)
        if run is not None and run.lifecycle_state is RunState.RECOVERY_PENDING:
            return "recovery_required"
        return "awaiting_effects"
    async def _effect_context(self, run_id: str) -> tuple[AgentIterationRequest, AgentIterationResult]:
        snapshots = await self._iterations.list_iteration_snapshots(run_id=run_id)
        if not snapshots:
            raise ValueError("E_AGENT_EFFECT_RESUME_ITERATION_MISSING")
        snapshot = max(snapshots, key=lambda item: item.binding.iteration_ordinal)
        if snapshot.result_payload is None or snapshot.decision_payload is None:
            raise ValueError("E_AGENT_EFFECT_RESUME_DECISION_MISSING")
        if (snapshot.decision_payload.get("rule") not in RESUMABLE_AGENT_RULES
                or not snapshot.decision_inputs or not snapshot.decision_inputs.get("valid_recorded_result")):
            raise ValueError("E_AGENT_EFFECT_RESUME_REASON_INVALID")
        return AgentIterationRequest.from_wire(dict(snapshot.request_payload)), AgentIterationResult.from_wire(
            dict(snapshot.result_payload)
        )

    async def _safe_receipts(
        self,
        result: AgentIterationResult,
    ) -> tuple[tuple[AgentEffectReceipt, ...] | None, tuple[EffectJournalEntryRecord, ...]]:
        entries = await self._publication.repository.list_effect_journal_entries(
            run_id=result.identity.run_id
        )
        by_effect = {entry.effect_id: entry for entry in entries}
        receipts: list[AgentEffectReceipt] = []
        selected = []
        for proposal in result.effect_proposals:
            entry = by_effect.get(f"agent-effect:{proposal.proposal_id}")
            if (
                entry is None
                or entry.observed_result_ref is None
                or entry.uncertainty_classification is not ResidualUncertaintyClassification.NONE
            ):
                return None, ()
            receipts.append(
                effect_receipt(
                    proposal,
                    "observed",
                    entry.authorization_basis_ref,
                    (entry.observed_result_ref, entry.journal_entry_id),
                )
            )
            selected.append(entry)
        return tuple(receipts), tuple(selected)

    async def _run_creation_timestamp(self, run_id: str) -> str:
        run = await self._execution.get_run_record(run_id=run_id)
        if run is None:
            raise ValueError("E_AGENT_EFFECT_RUN_AUTHORITY_MISSING")
        return str(run.creation_timestamp)

    async def _enqueue_resume(
        self,
        *,
        request: AgentIterationRequest,
        run_creation_timestamp_utc: str,
        decision_timestamps_utc: Sequence[str],
        next_lease_expiries_utc: Sequence[str],
        created_at_utc: str,
        continuation_inputs: Mapping[str, Any],
    ) -> GovernedAgentWakeEnqueueResult:
        request_digest = agent_payload_digest(request.to_wire())
        submission = GovernedAgentWakeSubmission.from_mapping(
            {
                "occurrence_id": (
                    f"effect-resume:{request.identity.run_id}:{request.identity.iteration_ordinal}:"
                    f"{request_digest.removeprefix('sha256:')[:16]}"
                ),
                "target_kind": "existing_run",
                "target_run_id": request.identity.run_id,
                "workload_id": None,
                "dispatch": {
                    "schema_version": "governed_agent_wake_dispatch.v1",
                    "request": request.to_wire(),
                    "creation_timestamp_utc": run_creation_timestamp_utc,
                    "decision_timestamps_utc": list(decision_timestamps_utc),
                    "next_lease_expiries_utc": list(next_lease_expiries_utc),
                    "continuation_inputs": dict(continuation_inputs),
                },
            }
        )
        wake = await self._wakes.enqueue(
            submission.to_request(source="api", created_at_utc=created_at_utc)
        )
        if wake.status == "conflict" or wake.wake is None:
            raise ValueError("E_AGENT_EFFECT_RESUME_WAKE_CONFLICT")
        notify_wake_ready(result=wake, notify_ready=self._notify_ready)
        return wake




__all__ = ["GovernedAgentEffectControlResult", "GovernedAgentEffectControlService"]
