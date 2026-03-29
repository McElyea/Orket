from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from orket.application.services.control_plane_workload_catalog import KERNEL_ACTION_WORKLOAD
from orket.application.services.control_plane_resource_authority_checks import (
    require_resource_snapshot_matches_lease,
)
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_failure import (
    publish_failed_commit_recovery_decision,
    publish_pre_effect_terminal_commit_recovery_decision,
)
from orket.application.services.kernel_action_control_plane_outcome import (
    enter_attempt_execution_if_needed,
    finalize_attempt_from_commit,
    publish_final_truth_for_commit,
)
from orket.application.services.kernel_action_control_plane_resource_lifecycle import (
    ensure_active_execution_lease,
    lease_id_for_run,
    reservation_id_for_run,
    resource_id_for_run,
    ensure_admission_reservation,
    release_execution_authority_if_present,
)
from orket.application.services.control_plane_snapshot_publication import publish_run_snapshots
from orket.application.services.kernel_action_control_plane_support import (
    admission_receipt_ref,
    attempt_id_for,
    configuration_snapshot_id_for,
    event_digest_for,
    event_result_ref,
    event_timestamp_for,
    has_observed_execution,
    optional_text,
    policy_snapshot_id_for,
    proposal_digest_for,
    publish_effect_from_commit_if_missing,
    publish_step_from_commit_if_missing,
    required_text,
    resolve_namespace_scope_for_request,
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
    is_terminal_attempt_state,
    is_terminal_run_state,
    validate_attempt_state_transition,
    validate_run_state_transition,
)


class KernelActionControlPlaneError(ValueError):
    """Raised when the governed action path cannot publish control-plane truth honestly."""


class KernelActionControlPlaneService:
    """Publishes per-trace governed kernel actions into the control-plane store."""

    WORKLOAD = KERNEL_ACTION_WORKLOAD
    ALLOWED_COMMIT_STATUSES = frozenset({"COMMITTED", "REJECTED_POLICY", "ERROR"})
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
        namespace_scope = resolve_namespace_scope_for_request(request=request)

        run = await self.execution_repository.get_run_record(run_id=run_id)
        attempt = await self.execution_repository.get_attempt_record(attempt_id=attempt_id)
        if run is None:
            policy_payload = {
                "decision_digest": decision_digest,
                "admission_decision": dict(response.get("admission_decision") or {}),
                "namespace_scope_rule": "session_scoped_kernel_action",
            }
            configuration_payload = {
                "proposal_digest": proposal_digest,
                "proposal": dict(request.get("proposal") or {}),
                "session_id": session_id,
                "trace_id": trace_id,
                "namespace_scope": namespace_scope,
            }
            run = RunRecord(
                run_id=run_id,
                workload_id=self.WORKLOAD.workload_id,
                workload_version=self.WORKLOAD.workload_version,
                policy_snapshot_id=self.policy_snapshot_id_for(session_id=session_id, trace_id=trace_id),
                policy_digest=decision_digest,
                configuration_snapshot_id=self.configuration_snapshot_id_for(session_id=session_id, trace_id=trace_id),
                configuration_digest=proposal_digest,
                creation_timestamp=created_at,
                admission_decision_receipt_ref=admission_receipt_ref(
                    response=response,
                    ledger_items=ledger_items,
                ),
                namespace_scope=namespace_scope,
                lifecycle_state=RunState.ADMITTED,
                current_attempt_id=attempt_id,
            )
            await publish_run_snapshots(
                publication=self.publication,
                run=run,
                policy_payload=policy_payload,
                policy_source_refs=[run.admission_decision_receipt_ref],
                configuration_payload=configuration_payload,
                configuration_source_refs=[run.admission_decision_receipt_ref],
            )
            await self.execution_repository.save_run_record(record=run)
        else:
            attempt = await self._require_consistent_existing_run_attempt(
                run=run,
                attempt=attempt,
                expected_attempt_id=attempt_id,
            )
            existing_scope = str(run.namespace_scope or "").strip()
            if existing_scope and existing_scope != namespace_scope:
                raise KernelActionControlPlaneError(
                    "kernel-action run namespace scope mismatch for existing run: "
                    f"run_scope={existing_scope!r} request_scope={namespace_scope!r}"
                )
            if not existing_scope:
                run = run.model_copy(update={"namespace_scope": namespace_scope})
                await self.execution_repository.save_run_record(record=run)
        if run is not None:
            await ensure_admission_reservation(publication=self.publication, run=run)
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

    async def _require_consistent_existing_run_attempt(
        self,
        *,
        run: RunRecord,
        attempt: AttemptRecord | None,
        expected_attempt_id: str,
    ) -> AttemptRecord:
        current_attempt_id = str(run.current_attempt_id or "").strip()
        if not current_attempt_id:
            raise KernelActionControlPlaneError(f"kernel-action run missing current attempt id: {run.run_id}")
        if current_attempt_id != expected_attempt_id:
            raise KernelActionControlPlaneError(
                "kernel-action run current attempt mismatch: "
                f"run_current_attempt={current_attempt_id!r} expected={expected_attempt_id!r}"
            )
        resolved_attempt = attempt
        if resolved_attempt is None:
            resolved_attempt = await self.execution_repository.get_attempt_record(attempt_id=current_attempt_id)
        if resolved_attempt is None:
            raise KernelActionControlPlaneError(
                f"kernel-action run current attempt record missing: {run.run_id}:{current_attempt_id}"
            )
        run_terminal = is_terminal_run_state(run.lifecycle_state)
        attempt_terminal = is_terminal_attempt_state(resolved_attempt.attempt_state)
        if run_terminal and run.final_truth_record_id is None:
            raise KernelActionControlPlaneError(f"kernel-action terminal run missing final truth: {run.run_id}")
        if run_terminal and not attempt_terminal:
            raise KernelActionControlPlaneError(
                f"kernel-action terminal run has non-terminal attempt: {run.run_id}:{resolved_attempt.attempt_id}"
            )
        if not run_terminal and attempt_terminal:
            raise KernelActionControlPlaneError(
                f"kernel-action active run has terminal attempt drift: {run.run_id}:{resolved_attempt.attempt_id}"
            )
        await self._require_existing_resource_authority(run=run)
        return resolved_attempt

    async def _require_existing_resource_authority(self, *, run: RunRecord) -> None:
        reservation = await self.publication.repository.get_latest_reservation_record(
            reservation_id=reservation_id_for_run(run_id=run.run_id)
        )
        lease = await self.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
        if lease is None:
            return
        if reservation is None:
            raise KernelActionControlPlaneError(
                f"kernel-action run has lease authority without reservation: {run.run_id}"
            )
        if lease.source_reservation_id != reservation.reservation_id:
            raise KernelActionControlPlaneError(
                f"kernel-action run lease source mismatch: {run.run_id}"
            )
        resource = await self.publication.repository.get_latest_resource_record(
            resource_id=resource_id_for_run(run=run)
        )
        require_resource_snapshot_matches_lease(
            resource=resource,
            lease=lease,
            expected_resource_kind="kernel_action_scope",
            expected_namespace_scope=str(run.namespace_scope or "").strip(),
            error_context=f"kernel-action run {run.run_id}",
            error_factory=KernelActionControlPlaneError,
        )

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
        if status not in self.ALLOWED_COMMIT_STATUSES:
            raise KernelActionControlPlaneError(
                f"unsupported governed action commit status for control-plane publication: {status}"
            )
        committed_at = event_timestamp_for(ledger_items, "commit.recorded") or utc_now()
        observed_execution = has_observed_execution(request=request, ledger_items=ledger_items)
        claimed_result = bool(optional_text(request, "execution_result_digest"))
        existing_final_truth = await self.publication.repository.get_final_truth(run_id=run.run_id)
        if run.final_truth_record_id is not None and existing_final_truth is not None:
            existing_effects = await self.publication.repository.list_effect_journal_entries(run_id=run.run_id)
            return run, attempt, existing_final_truth, (existing_effects[-1] if existing_effects else None)
        if run.lifecycle_state is not RunState.EXECUTING:
            validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.EXECUTING)
            run = run.model_copy(update={"lifecycle_state": RunState.EXECUTING})
            await self.execution_repository.save_run_record(record=run)
        if status == "COMMITTED" or observed_execution:
            await ensure_active_execution_lease(
                publication=self.publication,
                run=run,
                publication_timestamp=committed_at,
            )
        attempt = await enter_attempt_execution_if_needed(
            execution_repository=self.execution_repository,
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
                namespace_scope=str(run.namespace_scope or "").strip() or None,
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

        terminal_attempt = await finalize_attempt_from_commit(
            execution_repository=self.execution_repository,
            attempt=attempt,
            run_id=run.run_id,
            status=status,
            committed_at=committed_at,
            observed_execution=observed_execution,
        )
        if terminal_attempt.attempt_state is AttemptState.FAILED:
            terminal_attempt = await publish_failed_commit_recovery_decision(
                execution_repository=self.execution_repository,
                publication=self.publication,
                run=run,
                attempt=terminal_attempt,
                status=status,
                rationale_ref=event_result_ref(ledger_items, "commit.recorded", response),
            )
        elif status != "COMMITTED" and terminal_attempt.attempt_state is AttemptState.ABANDONED:
            terminal_attempt = await publish_pre_effect_terminal_commit_recovery_decision(
                execution_repository=self.execution_repository,
                publication=self.publication,
                run=run,
                attempt=terminal_attempt,
                status=status,
                rationale_ref=event_result_ref(ledger_items, "commit.recorded", response),
            )
        final_truth = await publish_final_truth_for_commit(
            publication=self.publication,
            run_id=run.run_id,
            request=request,
            response=response,
            status=status,
            observed_execution=observed_execution,
        )
        next_state = RunState.COMPLETED if status == "COMMITTED" else RunState.FAILED_TERMINAL
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=next_state)
        terminal_run = run.model_copy(
            update={"lifecycle_state": next_state, "final_truth_record_id": final_truth.final_truth_record_id}
        )
        await self.execution_repository.save_run_record(record=terminal_run)
        await release_execution_authority_if_present(
            publication=self.publication,
            run=terminal_run,
            release_basis=f"kernel_action_commit_terminal:{status.lower()}",
            publication_timestamp=committed_at,
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
        if attempt is not None and not is_terminal_attempt_state(attempt.attempt_state):
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
        await release_execution_authority_if_present(
            publication=self.publication,
            run=updated_run,
            release_basis="kernel_action_session_end_cancelled",
            publication_timestamp=ended_at,
        )
        return updated_run, updated_attempt, final_truth

__all__ = [
    "KernelActionControlPlaneError",
    "KernelActionControlPlaneService",
]
