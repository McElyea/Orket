from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_support import (
    admission_receipt_ref,
    attempt_id_for,
    authority_sources_for_commit,
    authorization_basis_ref,
    configuration_snapshot_id_for,
    event_digest_for,
    event_result_ref,
    event_timestamp_for,
    final_truth_projection_for_commit,
    has_observed_execution,
    has_validation_evidence,
    optional_text,
    policy_snapshot_id_for,
    proposal_digest_for,
    publish_effect_from_commit_if_missing,
    publish_step_from_commit_if_missing,
    required_text,
    run_id_for,
    should_publish_step_for_commit,
    starting_snapshot_ref_for,
    step_id_for,
    utc_now,
)
from orket.core.contracts import AttemptRecord, EffectJournalEntryRecord, FinalTruthRecord, RunRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    validate_attempt_state_transition,
    validate_run_state_transition,
)


class KernelActionControlPlaneError(ValueError):
    """Raised when the governed action path cannot publish control-plane truth honestly."""


class KernelActionControlPlaneService:
    """Publishes per-trace governed kernel actions into the control-plane store."""

    WORKLOAD_ID = "kernel-action-path"
    WORKLOAD_VERSION = "kernel_api.v1"
    run_id_for = staticmethod(run_id_for)
    attempt_id_for = staticmethod(attempt_id_for)
    policy_snapshot_id_for = staticmethod(policy_snapshot_id_for)
    configuration_snapshot_id_for = staticmethod(configuration_snapshot_id_for)
    starting_snapshot_ref_for = staticmethod(starting_snapshot_ref_for)
    step_id_for = staticmethod(step_id_for)

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        publication: ControlPlanePublicationService,
    ) -> None:
        self.execution_repository = execution_repository
        self.publication = publication

    async def record_admission(
        self,
        *,
        request: dict[str, Any],
        response: dict[str, Any],
        ledger_items: Sequence[dict[str, Any]] = (),
    ) -> tuple[RunRecord, AttemptRecord]:
        session_id = required_text(request, "session_id")
        trace_id = required_text(request, "trace_id")
        proposal_digest = proposal_digest_for(request=request, response=response)
        decision_digest = required_text(response, "decision_digest")
        created_at = event_timestamp_for(ledger_items, "admission.decided") or utc_now()
        run_id = self.run_id_for(session_id=session_id, trace_id=trace_id)
        attempt_id = self.attempt_id_for(session_id=session_id, trace_id=trace_id)

        run = await self.execution_repository.get_run_record(run_id=run_id)
        attempt = await self.execution_repository.get_attempt_record(attempt_id=attempt_id)
        if run is None:
            run = RunRecord(
                run_id=run_id,
                workload_id=self.WORKLOAD_ID,
                workload_version=self.WORKLOAD_VERSION,
                policy_snapshot_id=self.policy_snapshot_id_for(session_id=session_id, trace_id=trace_id),
                policy_digest=decision_digest,
                configuration_snapshot_id=self.configuration_snapshot_id_for(session_id=session_id, trace_id=trace_id),
                configuration_digest=proposal_digest,
                creation_timestamp=created_at,
                admission_decision_receipt_ref=admission_receipt_ref(
                    response=response,
                    ledger_items=ledger_items,
                ),
                lifecycle_state=RunState.ADMITTED,
                current_attempt_id=attempt_id,
            )
            await self.execution_repository.save_run_record(record=run)
        if attempt is None:
            attempt = AttemptRecord(
                attempt_id=attempt_id,
                run_id=run_id,
                attempt_ordinal=1,
                attempt_state=AttemptState.CREATED,
                starting_state_snapshot_ref=self.starting_snapshot_ref_for(
                    session_id=session_id,
                    trace_id=trace_id,
                    proposal_digest=proposal_digest,
                ),
                start_timestamp=created_at,
            )
            await self.execution_repository.save_attempt_record(record=attempt)
        return run, attempt

    async def record_commit(
        self,
        *,
        request: dict[str, Any],
        response: dict[str, Any],
        ledger_items: Sequence[dict[str, Any]] = (),
    ) -> tuple[RunRecord, AttemptRecord, FinalTruthRecord, EffectJournalEntryRecord | None]:
        run, attempt = await self.record_admission(
            request=request,
            response={
                "proposal_digest": proposal_digest_for(request=request, response=response),
                "decision_digest": required_text(request, "admission_decision_digest"),
                "event_digest": event_digest_for(ledger_items, "admission.decided"),
            },
            ledger_items=ledger_items,
        )
        status = required_text(response, "status")
        committed_at = event_timestamp_for(ledger_items, "commit.recorded") or utc_now()
        observed_execution = has_observed_execution(request=request, ledger_items=ledger_items)
        claimed_result = bool(optional_text(request, "execution_result_digest"))
        existing_final_truth = await self.publication.repository.get_final_truth(run_id=run.run_id)
        if run.final_truth_record_id is not None and existing_final_truth is not None:
            existing_effects = await self.publication.repository.list_effect_journal_entries(run_id=run.run_id)
            return run, attempt, existing_final_truth, (existing_effects[-1] if existing_effects else None)

        run = await self._move_run_to_executing(run=run)
        attempt = await self._enter_attempt_execution_if_needed(
            attempt=attempt,
            run_id=run.run_id,
            execution_timestamp=committed_at,
            allow_claim_only=status == "COMMITTED" and claimed_result,
            observed_execution=observed_execution,
        )

        if should_publish_step_for_commit(
            status=status,
            observed_execution=observed_execution,
            claimed_result=claimed_result,
            request=request,
        ) and attempt.attempt_state is AttemptState.EXECUTING:
            await publish_step_from_commit_if_missing(
                execution_repository=self.execution_repository,
                run_id=run.run_id,
                attempt_id=attempt.attempt_id,
                request=request,
                response=response,
                ledger_items=ledger_items,
                status=status,
                observed_execution=observed_execution,
            )

        effect_entry = None
        if should_publish_step_for_commit(
            status=status,
            observed_execution=observed_execution,
            claimed_result=claimed_result,
            request=request,
        ):
            effect_entry = await publish_effect_from_commit_if_missing(
                publication=self.publication,
                run_id=run.run_id,
                attempt_id=attempt.attempt_id,
                request=request,
                response=response,
                committed_at=committed_at,
                ledger_items=ledger_items,
            )

        terminal_attempt = await self._finalize_attempt_from_commit(
            attempt=attempt,
            run_id=run.run_id,
            status=status,
            committed_at=committed_at,
            observed_execution=observed_execution,
        )
        final_truth = await self._publish_final_truth_for_commit(
            run_id=run.run_id,
            request=request,
            response=response,
            status=status,
            observed_execution=observed_execution,
        )
        terminal_run = await self._finalize_run_from_commit(
            run=run,
            status=status,
            final_truth_record_id=final_truth.final_truth_record_id,
        )
        return terminal_run, terminal_attempt, final_truth, effect_entry

    async def record_session_end(
        self,
        *,
        request: dict[str, Any],
        response: dict[str, Any],
        ledger_items: Sequence[dict[str, Any]] = (),
    ) -> tuple[RunRecord, AttemptRecord | None, FinalTruthRecord] | None:
        session_id = required_text(request, "session_id")
        trace_id = required_text(request, "trace_id")
        run = await self.execution_repository.get_run_record(
            run_id=self.run_id_for(session_id=session_id, trace_id=trace_id)
        )
        if run is None or run.final_truth_record_id is not None:
            return None
        ended_at = event_timestamp_for(ledger_items, "session.ended") or utc_now()
        attempt = await self.execution_repository.get_attempt_record(
            attempt_id=self.attempt_id_for(session_id=session_id, trace_id=trace_id)
        )
        updated_attempt = attempt
        if attempt is not None and attempt.attempt_state is AttemptState.CREATED:
            validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.ABANDONED)
            updated_attempt = attempt.model_copy(update={"attempt_state": AttemptState.ABANDONED, "end_timestamp": ended_at})
            await self.execution_repository.save_attempt_record(record=updated_attempt)
        final_truth = await self.publication.publish_final_truth(
            final_truth_record_id=f"kernel-action-final-truth:{run.run_id}",
            run_id=run.run_id,
            result_class=ResultClass.BLOCKED,
            completion_classification=CompletionClassification.UNSATISFIED,
            evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
            residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
            degradation_classification=DegradationClassification.NONE,
            closure_basis=ClosureBasisClassification.CANCELLED_BY_AUTHORITY,
            authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
            authoritative_result_ref=event_result_ref(ledger_items, "session.ended", response),
        )
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.CANCELLED)
        updated_run = run.model_copy(
            update={
                "lifecycle_state": RunState.CANCELLED,
                "final_truth_record_id": final_truth.final_truth_record_id,
            }
        )
        await self.execution_repository.save_run_record(record=updated_run)
        return updated_run, updated_attempt, final_truth

    async def _move_run_to_executing(self, *, run: RunRecord) -> RunRecord:
        if run.lifecycle_state is RunState.EXECUTING:
            return run
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.EXECUTING)
        updated = run.model_copy(update={"lifecycle_state": RunState.EXECUTING})
        await self.execution_repository.save_run_record(record=updated)
        return updated

    async def _enter_attempt_execution_if_needed(
        self,
        *,
        attempt: AttemptRecord,
        run_id: str,
        execution_timestamp: str,
        allow_claim_only: bool,
        observed_execution: bool,
    ) -> AttemptRecord:
        if attempt.attempt_state is AttemptState.EXECUTING:
            return attempt
        if attempt.attempt_state is not AttemptState.CREATED:
            raise KernelActionControlPlaneError(f"unexpected attempt state for governed action {run_id}")
        if not allow_claim_only and not observed_execution:
            return attempt
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.EXECUTING)
        updated = attempt.model_copy(update={"attempt_state": AttemptState.EXECUTING, "start_timestamp": execution_timestamp})
        await self.execution_repository.save_attempt_record(record=updated)
        return updated

    async def _finalize_attempt_from_commit(
        self,
        *,
        attempt: AttemptRecord,
        run_id: str,
        status: str,
        committed_at: str,
        observed_execution: bool,
    ) -> AttemptRecord:
        if status == "COMMITTED":
            if attempt.attempt_state is AttemptState.CREATED:
                attempt = await self._enter_attempt_execution_if_needed(
                    attempt=attempt,
                    run_id=run_id,
                    execution_timestamp=committed_at,
                    allow_claim_only=True,
                    observed_execution=observed_execution,
                )
            validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.COMPLETED)
            updated = attempt.model_copy(update={"attempt_state": AttemptState.COMPLETED, "end_timestamp": committed_at})
            await self.execution_repository.save_attempt_record(record=updated)
            return updated
        if observed_execution:
            if attempt.attempt_state is AttemptState.CREATED:
                attempt = await self._enter_attempt_execution_if_needed(
                    attempt=attempt,
                    run_id=run_id,
                    execution_timestamp=committed_at,
                    allow_claim_only=False,
                    observed_execution=True,
                )
            validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.FAILED)
            updated = attempt.model_copy(update={"attempt_state": AttemptState.FAILED, "end_timestamp": committed_at})
            await self.execution_repository.save_attempt_record(record=updated)
            return updated
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.ABANDONED)
        updated = attempt.model_copy(update={"attempt_state": AttemptState.ABANDONED, "end_timestamp": committed_at})
        await self.execution_repository.save_attempt_record(record=updated)
        return updated

    async def _finalize_run_from_commit(
        self,
        *,
        run: RunRecord,
        status: str,
        final_truth_record_id: str,
    ) -> RunRecord:
        next_state = RunState.COMPLETED if status == "COMMITTED" else RunState.FAILED_TERMINAL
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=next_state)
        updated = run.model_copy(update={"lifecycle_state": next_state, "final_truth_record_id": final_truth_record_id})
        await self.execution_repository.save_run_record(record=updated)
        return updated

    async def _publish_final_truth_for_commit(
        self,
        *,
        run_id: str,
        request: dict[str, Any],
        response: dict[str, Any],
        status: str,
        observed_execution: bool,
    ) -> FinalTruthRecord:
        existing = await self.publication.repository.get_final_truth(run_id=run_id)
        if existing is not None:
            return existing
        result_class, completion, evidence, residual, closure = final_truth_projection_for_commit(
            status=status,
            observed_execution=observed_execution,
            validated=has_validation_evidence(request=request, response=response, ledger_items=()),
            claimed_result=bool(optional_text(request, "execution_result_digest")),
        )
        authoritative_result_ref = optional_text(request, "execution_result_digest")
        if authoritative_result_ref:
            authoritative_result_ref = f"kernel-execution-result:{authoritative_result_ref}"
        else:
            authoritative_result_ref = required_text(response, "commit_event_digest")
        return await self.publication.publish_final_truth(
            final_truth_record_id=f"kernel-action-final-truth:{run_id}",
            run_id=run_id,
            result_class=result_class,
            completion_classification=completion,
            evidence_sufficiency_classification=evidence,
            residual_uncertainty_classification=residual,
            degradation_classification=DegradationClassification.NONE,
            closure_basis=closure,
            authority_sources=authority_sources_for_commit(evidence=evidence),
            authoritative_result_ref=authoritative_result_ref,
        )

__all__ = [
    "KernelActionControlPlaneError",
    "KernelActionControlPlaneService",
]
