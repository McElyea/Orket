from __future__ import annotations

from typing import Any

from orket.application.services.control_plane_workload_catalog import TURN_TOOL_WORKLOAD
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_snapshot_publication import publish_run_snapshots
from orket.application.services.turn_tool_control_plane_closeout import (
    ensure_begin_execution_allowed,
    ensure_current_execution_target,
    finalize_turn_execution,
    terminal_blocked_actions,
)
from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    TurnToolControlPlaneResourceError,
    ensure_active_execution_lease,
    ensure_admission_reservation,
    invalidate_admission_reservation_if_present,
    release_execution_authority_if_present,
)
from orket.application.services.turn_tool_control_plane_recovery import recover_pre_effect_attempt_for_resume_mode
from orket.application.services.turn_tool_control_plane_state_gate import (
    ensure_existing_run_allows_execution,
    existing_effect_for_operation,
)
from orket.application.services.turn_tool_control_plane_support import (
    attempt_id_for,
    capability_for,
    digest,
    effect_id_for,
    preflight_result_ref,
    resource_refs,
    run_id_for,
    run_namespace_scope,
    step_result_classification,
    tool_authorization_ref,
    tool_call_ref,
    tool_operation_ref,
    tool_result_ref,
    utc_now,
)
from orket.core.contracts import AttemptRecord, EffectJournalEntryRecord, FinalTruthRecord, RunRecord, StepRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    SideEffectBoundaryClass,
    is_terminal_attempt_state,
    validate_attempt_state_transition,
    validate_run_state_transition,
)

class TurnToolControlPlaneError(ValueError):
    """Raised when governed turn-tool control-plane truth cannot be published honestly."""

class TurnToolControlPlaneService:
    """Publishes governed turn-tool execution into first-class ControlPlane records."""

    WORKLOAD = TURN_TOOL_WORKLOAD

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        publication: ControlPlanePublicationService,
    ) -> None:
        self.execution_repository = execution_repository
        self.publication = publication

    async def publish_preflight_failure(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        proposal_hash: str,
        violation_reasons: list[str],
    ) -> tuple[RunRecord, FinalTruthRecord]:
        run = await self._ensure_admission_pending_run(session_id=session_id, issue_id=issue_id, role_name=role_name, turn_index=turn_index, proposal_hash=proposal_hash)
        existing_truth = await self.publication.repository.get_final_truth(run_id=run.run_id)
        if existing_truth is not None:
            if run.final_truth_record_id != existing_truth.final_truth_record_id:
                run = run.model_copy(update={"final_truth_record_id": existing_truth.final_truth_record_id})
                await self.execution_repository.save_run_record(record=run)
            return run, existing_truth
        preflight_ref = preflight_result_ref(run_id=run.run_id, violation_reasons=violation_reasons)
        current_attempt = await self._current_attempt_for_run(run=run)
        if current_attempt is None:
            current_attempt = await self._ensure_attempt(run=run)
        if current_attempt is not None and not is_terminal_attempt_state(current_attempt.attempt_state):
            closed_at = utc_now()
            decision = None
            if current_attempt.recovery_decision_id is None:
                decision = await self.publication.publish_recovery_decision(
                    decision_id=f"turn-tool-recovery:{run.run_id}:preflight:{current_attempt.attempt_ordinal:04d}",
                    run_id=run.run_id,
                    failed_attempt_id=current_attempt.attempt_id,
                    failure_classification_basis="tool_execution_blocked",
                    side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
                    recovery_policy_ref=run.policy_snapshot_id,
                    authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
                    rationale_ref=preflight_ref,
                    required_precondition_refs=[preflight_ref],
                    blocked_actions=terminal_blocked_actions(),
                )
            validate_attempt_state_transition(current_state=current_attempt.attempt_state, next_state=AttemptState.ABANDONED)
            current_attempt = current_attempt.model_copy(
                update={
                    "attempt_state": AttemptState.ABANDONED,
                    "end_timestamp": closed_at,
                    "side_effect_boundary_class": SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
                    "failure_class": "tool_execution_blocked",
                    "failure_plane": current_attempt.failure_plane if decision is None else decision.failure_plane,
                    "failure_classification": (
                        current_attempt.failure_classification
                        if decision is None
                        else decision.failure_classification
                    ),
                    "recovery_decision_id": (
                        current_attempt.recovery_decision_id
                        if decision is None
                        else decision.decision_id
                    ),
                }
            )
            await self.execution_repository.save_attempt_record(record=current_attempt)
        truth = await self.publication.publish_final_truth(
            final_truth_record_id=f"turn-tool-final-truth:{run.run_id}",
            run_id=run.run_id,
            result_class=ResultClass.BLOCKED,
            completion_classification=CompletionClassification.UNSATISFIED,
            evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
            residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
            degradation_classification=DegradationClassification.NONE,
            closure_basis=ClosureBasisClassification.POLICY_TERMINAL_STOP,
            authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
            authoritative_result_ref=preflight_ref,
        )
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.FAILED_TERMINAL)
        updated_run = run.model_copy(update={"lifecycle_state": RunState.FAILED_TERMINAL, "final_truth_record_id": truth.final_truth_record_id})
        await self.execution_repository.save_run_record(record=updated_run)
        try:
            await invalidate_admission_reservation_if_present(publication=self.publication, run=updated_run, invalidation_basis="turn_tool_preflight_terminal_stop")
        except TurnToolControlPlaneResourceError:
            await release_execution_authority_if_present(publication=self.publication, run=updated_run, release_basis="turn_tool_preflight_terminal_stop", publication_timestamp=utc_now())
        return updated_run, truth

    async def begin_execution(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        proposal_hash: str,
        resume_mode: bool = False,
    ) -> tuple[RunRecord, AttemptRecord]:
        run = await self._ensure_admission_pending_run(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            proposal_hash=proposal_hash,
        )
        existing_truth = await ensure_existing_run_allows_execution(
            execution_repository=self.execution_repository,
            publication=self.publication,
            run=run,
            error_type=TurnToolControlPlaneError,
        )
        if existing_truth is not None:
            truth = await self.publication.repository.get_final_truth(run_id=run.run_id)
            if truth is None:
                truth = existing_truth
            attempt = await self._current_attempt_for_run(run=run)
            if attempt is None:
                raise TurnToolControlPlaneError(f"finalized governed tool run missing attempt: {run.run_id}")
            return run, attempt

        current_attempt = await self._current_attempt_for_run(run=run)
        if resume_mode and current_attempt is not None:
            run, current_attempt = await recover_pre_effect_attempt_for_resume_mode(
                execution_repository=self.execution_repository,
                publication=self.publication,
                run=run,
                current_attempt=current_attempt,
            )
            return run, current_attempt

        ensure_begin_execution_allowed(
            run=run,
            current_attempt=current_attempt,
            error_type=TurnToolControlPlaneError,
        )
        attempt = current_attempt or await self._ensure_attempt(run=run)
        if run.lifecycle_state is RunState.ADMISSION_PENDING:
            await ensure_admission_reservation(publication=self.publication, run=run)
            validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.ADMITTED)
            run = run.model_copy(update={"lifecycle_state": RunState.ADMITTED})
            await self.execution_repository.save_run_record(record=run)
        if run.lifecycle_state is RunState.ADMITTED:
            await ensure_active_execution_lease(
                publication=self.publication,
                run=run,
                publication_timestamp=utc_now(),
            )
            validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.EXECUTING)
            run = run.model_copy(update={"lifecycle_state": RunState.EXECUTING})
            await self.execution_repository.save_run_record(record=run)
        if attempt.attempt_state is AttemptState.CREATED:
            validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.EXECUTING)
            attempt = attempt.model_copy(update={"attempt_state": AttemptState.EXECUTING})
            await self.execution_repository.save_attempt_record(record=attempt)
        return run, attempt

    async def publish_step_result(
        self,
        *,
        run_id: str,
        attempt_id: str,
        step_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        result: dict[str, Any],
        binding: dict[str, Any] | None,
        operation_id: str,
        replayed: bool,
    ) -> tuple[StepRecord, EffectJournalEntryRecord]:
        run = await self._require_run(run_id=run_id)
        existing = await self.execution_repository.get_step_record(step_id=step_id)
        existing_effect = await existing_effect_for_operation(
            publication=self.publication,
            run_id=run_id,
            effect_id=effect_id_for(operation_id=operation_id),
        )
        if run.final_truth_record_id is not None:
            if existing is not None and existing_effect is not None:
                return existing, existing_effect
            raise TurnToolControlPlaneError(
                f"finalized governed turn run cannot publish new step truth: {run.run_id}"
            )
        attempt = await self._require_attempt(attempt_id=attempt_id)
        ensure_current_execution_target(
            run=run,
            attempt=attempt,
            operation_name="publish_step_result",
            error_type=TurnToolControlPlaneError,
        )
        tool_call_digest = digest(
            {"tool_name": tool_name, "tool_args": tool_args, "binding": dict(binding or {}), "operation_id": operation_id}
        )
        if existing is None:
            existing = await self.execution_repository.save_step_record(
                record=StepRecord(
                    step_id=step_id,
                    attempt_id=attempt_id,
                    step_kind="governed_tool_operation",
                    namespace_scope=run.namespace_scope,
                    input_ref=tool_call_ref(tool_call_digest=tool_call_digest),
                    output_ref=tool_result_ref(operation_id=operation_id),
                    capability_used=capability_for(tool_name=tool_name, binding=binding),
                    resources_touched=resource_refs(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        result=result,
                        namespace_scope=run.namespace_scope,
                    ),
                    observed_result_classification=step_result_classification(result=result, replayed=replayed),
                    receipt_refs=[
                        tool_operation_ref(operation_id=operation_id),
                        tool_call_ref(tool_call_digest=tool_call_digest),
                    ],
                    closure_classification="step_completed" if bool(result.get("ok", False)) else "step_failed",
                )
            )
        if existing_effect is not None:
            return existing, existing_effect
        record = StepRecord(
            step_id=existing.step_id,
            attempt_id=existing.attempt_id,
            step_kind=existing.step_kind,
            namespace_scope=existing.namespace_scope,
            input_ref=existing.input_ref,
            output_ref=existing.output_ref,
            capability_used=existing.capability_used,
            resources_touched=existing.resources_touched,
            observed_result_classification=existing.observed_result_classification,
            receipt_refs=existing.receipt_refs,
            closure_classification=existing.closure_classification,
        )
        intended_target_ref = record.resources_touched[0] if record.resources_touched else f"tool:{tool_name}"
        effect = await self.publication.append_effect_journal_entry(
            journal_entry_id=f"turn-tool-journal:{operation_id}",
            effect_id=effect_id_for(operation_id=operation_id),
            run_id=run_id,
            attempt_id=attempt_id,
            step_id=step_id,
            authorization_basis_ref=tool_authorization_ref(tool_call_digest=tool_call_digest),
            publication_timestamp=utc_now(),
            intended_target_ref=intended_target_ref,
            observed_result_ref=tool_result_ref(operation_id=operation_id),
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref=tool_operation_ref(operation_id=operation_id),
        )
        return record, effect

    async def finalize_execution(
        self,
        *,
        run_id: str,
        attempt_id: str,
        authoritative_result_ref: str,
        violation_reasons: list[str],
        executed_step_count: int,
    ) -> tuple[RunRecord, AttemptRecord, FinalTruthRecord]:
        run = await self._require_run(run_id=run_id)
        attempt = await self._require_attempt(attempt_id=attempt_id)
        return await finalize_turn_execution(
            execution_repository=self.execution_repository,
            publication=self.publication,
            run=run,
            attempt=attempt,
            authoritative_result_ref=authoritative_result_ref,
            violation_reasons=violation_reasons,
            executed_step_count=executed_step_count,
            error_type=TurnToolControlPlaneError,
        )

    async def _ensure_admission_pending_run(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        proposal_hash: str,
    ) -> RunRecord:
        run_id = run_id_for(session_id=session_id, issue_id=issue_id, role_name=role_name, turn_index=turn_index)
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is not None:
            await ensure_admission_reservation(publication=self.publication, run=run)
            return run
        policy_payload = {"proposal_hash": proposal_hash, "governed": True}
        configuration_payload = {
            "session_id": session_id,
            "issue_id": issue_id,
            "role_name": role_name,
            "turn_index": turn_index,
            "proposal_hash": proposal_hash,
            "namespace_scope": run_namespace_scope(issue_id=issue_id),
        }
        record = RunRecord(
            run_id=run_id,
            workload_id=self.WORKLOAD.workload_id,
            workload_version=self.WORKLOAD.workload_version,
            policy_snapshot_id=f"turn-tool-policy:{run_id}",
            policy_digest=digest(policy_payload),
            configuration_snapshot_id=f"turn-tool-config:{run_id}",
            configuration_digest=digest(configuration_payload),
            creation_timestamp=utc_now(),
            admission_decision_receipt_ref=f"turn-tool-proposal:{proposal_hash}",
            namespace_scope=run_namespace_scope(issue_id=issue_id),
            lifecycle_state=RunState.ADMISSION_PENDING,
            current_attempt_id=attempt_id_for(run_id=run_id),
        )
        await publish_run_snapshots(
            publication=self.publication,
            run=record,
            policy_payload=policy_payload,
            policy_source_refs=[record.admission_decision_receipt_ref],
            configuration_payload=configuration_payload,
            configuration_source_refs=[record.admission_decision_receipt_ref],
        )
        run = await self.execution_repository.save_run_record(record=record)
        await ensure_admission_reservation(publication=self.publication, run=run)
        return run

    async def ensure_reentry_allowed(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
    ) -> None:
        run_id = run_id_for(session_id=session_id, issue_id=issue_id, role_name=role_name, turn_index=turn_index)
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None:
            return
        await ensure_existing_run_allows_execution(
            execution_repository=self.execution_repository,
            publication=self.publication,
            run=run,
            error_type=TurnToolControlPlaneError,
        )

    async def _ensure_attempt(self, *, run: RunRecord) -> AttemptRecord:
        attempt_id = attempt_id_for(run_id=run.run_id)
        attempt = await self.execution_repository.get_attempt_record(attempt_id=attempt_id)
        if attempt is not None:
            return attempt
        record = AttemptRecord(
            attempt_id=attempt_id,
            run_id=run.run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.CREATED,
            starting_state_snapshot_ref=f"turn-tool-input:{run.run_id}",
            start_timestamp=run.creation_timestamp,
        )
        return await self.execution_repository.save_attempt_record(record=record)

    async def _current_attempt_for_run(self, *, run: RunRecord) -> AttemptRecord | None:
        attempt_id = run.current_attempt_id or attempt_id_for(run_id=run.run_id)
        return await self.execution_repository.get_attempt_record(attempt_id=attempt_id)

    async def _require_run(self, *, run_id: str) -> RunRecord:
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None:
            raise TurnToolControlPlaneError(f"governed turn-tool run not found: {run_id}")
        return run

    async def _require_attempt(self, *, attempt_id: str) -> AttemptRecord:
        attempt = await self.execution_repository.get_attempt_record(attempt_id=attempt_id)
        if attempt is None:
            raise TurnToolControlPlaneError(f"governed turn-tool attempt not found: {attempt_id}")
        return attempt
from .turn_tool_control_plane_factory import build_turn_tool_control_plane_service

__all__ = ["TurnToolControlPlaneError", "TurnToolControlPlaneService", "build_turn_tool_control_plane_service"]
