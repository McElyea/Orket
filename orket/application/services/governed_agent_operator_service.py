from __future__ import annotations

from dataclasses import dataclass

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import AttemptRecord, FinalTruthRecord, OperatorActionRecord, RunRecord
from orket.core.contracts.control_plane_transaction import ControlPlaneTransaction, ControlPlaneTransactionFactory
from orket.core.contracts.governed_agent_ports import (
    GovernedAgentIterationInvoker,
    GovernedAgentIterationRepository,
    GovernedAgentIterationSnapshot,
)
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    OperatorCommandClass,
    OperatorInputClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
)


@dataclass(frozen=True, slots=True)
class GovernedAgentCancellationResult:
    run: RunRecord
    action: OperatorActionRecord
    final_truth: FinalTruthRecord
    child_confirmed_stopped: bool


class GovernedAgentOperatorService:
    def __init__(
        self,
        *,
        transactions: ControlPlaneTransactionFactory,
        iteration_repository: GovernedAgentIterationRepository,
        invoker: GovernedAgentIterationInvoker,
    ) -> None:
        self._transactions = transactions
        self._iterations = iteration_repository
        self._invoker = invoker

    async def cancel_run(
        self,
        *,
        run_id: str,
        action_id: str,
        actor_ref: str,
        timestamp_utc: str,
        reason: str,
        cancellation_epoch: int,
        grace_period_seconds: float,
    ) -> GovernedAgentCancellationResult:
        async with self._transactions() as transaction:
            run = await transaction.execution.get_run_record(run_id=run_id)
            if run is None:
                raise ValueError("E_AGENT_RUN_NOT_FOUND")
            if run.final_truth_record_id is not None or await transaction.records.get_final_truth(run_id=run_id):
                raise ValueError("E_AGENT_RUN_ALREADY_TERMINAL")
            attempt = await transaction.execution.get_attempt_record(attempt_id=run.current_attempt_id)
            if attempt is None or attempt.run_id != run.run_id or attempt.attempt_state is not AttemptState.EXECUTING:
                raise ValueError("E_AGENT_TERMINAL_AUTHORITY_CONFLICT")
            action = await self._publish_action(
                transaction=transaction, run=run, action_id=action_id,
                actor_ref=actor_ref, timestamp_utc=timestamp_utc,
            )
        snapshots = await self._iterations.list_iteration_snapshots(run_id=run_id)
        active = next((item for item in reversed(snapshots)
                       if item.binding.attempt_id == attempt.attempt_id and item.state in {"prepared", "cancelled"}), None)
        stopped, cancellation_ref = await self._cancel_active(
            active=active,
            cancellation_epoch=cancellation_epoch,
            reason=reason,
            grace_period_seconds=grace_period_seconds,
        )
        closed_run, truth = await self._close_cancelled(
            run=run, attempt=attempt, action=action, stopped=stopped,
            cancellation_ref=cancellation_ref, timestamp_utc=timestamp_utc,
        )
        return GovernedAgentCancellationResult(closed_run, action, truth, stopped)

    async def _publish_action(
        self,
        *,
        transaction: ControlPlaneTransaction,
        run: RunRecord,
        action_id: str,
        actor_ref: str,
        timestamp_utc: str,
    ) -> OperatorActionRecord:
        return await transaction.records.save_operator_action(
            record=OperatorActionRecord(
                action_id=action_id,
                actor_ref=actor_ref,
                input_class=OperatorInputClass.COMMAND,
                target_ref=run.run_id,
                timestamp=timestamp_utc,
                precondition_basis_ref=f"agent-run-state:{run.run_id}:{run.lifecycle_state.value}",
                result="accepted",
                command_class=OperatorCommandClass.CANCEL_RUN,
                affected_transition_refs=[f"agent-run-cancelled:{run.run_id}"],
            )
        )

    async def _cancel_active(
        self,
        *,
        active: GovernedAgentIterationSnapshot | None,
        cancellation_epoch: int,
        reason: str,
        grace_period_seconds: float,
    ) -> tuple[bool, str | None]:
        stopped = True
        cancellation_ref: str | None = None
        if active is not None:
            publication = await self._iterations.cancel_invocation(
                binding=active.binding,
                cancellation_epoch=cancellation_epoch,
                normalized_reason=reason,
            )
            if publication.status not in {"accepted", "idempotent"}:
                raise ValueError(f"E_AGENT_CANCELLATION_PUBLICATION_{publication.status.upper()}")
            cancellation_ref = publication.cancellation_ref
            stopped = await self._invoker.cancel_and_reap(
                binding=active.binding,
                cancellation_payload={
                    "object_type": "agent_cancellation",
                    "schema_version": "agent_cancellation.v1",
                    "requested": True,
                    "cancellation_epoch": cancellation_epoch,
                    "reason": reason,
                },
                grace_period_seconds=grace_period_seconds,
            )
        return stopped, cancellation_ref

    async def _close_cancelled(
        self, *, run: RunRecord, attempt: AttemptRecord, action: OperatorActionRecord,
        stopped: bool, cancellation_ref: str | None, timestamp_utc: str,
    ) -> tuple[RunRecord, FinalTruthRecord]:
        async with self._transactions() as transaction:
            current_run = await transaction.execution.get_run_record(run_id=run.run_id)
            current_attempt = await transaction.execution.get_attempt_record(attempt_id=attempt.attempt_id)
            if (current_run != run or current_attempt != attempt
                    or await transaction.records.get_final_truth(run_id=run.run_id) is not None):
                raise ValueError("E_AGENT_TERMINAL_AUTHORITY_CONFLICT")
            truth = await self._publish_cancelled_truth(
                publication=ControlPlanePublicationService(repository=transaction.records),
                run=run, action=action, child_confirmed_stopped=stopped, cancellation_ref=cancellation_ref,
            )
            attempt = await transaction.execution.save_attempt_record(record=attempt.model_copy(update={
                "attempt_state": AttemptState.INTERRUPTED, "end_timestamp": timestamp_utc,
                "failure_class": "operator_cancelled",
            }))
            closed_run = await transaction.execution.save_run_record(record=run.model_copy(update={
                "lifecycle_state": RunState.CANCELLED, "final_truth_record_id": truth.final_truth_record_id,
            }))
            return closed_run, truth

    async def _publish_cancelled_truth(
        self,
        *,
        publication: ControlPlanePublicationService,
        run: RunRecord,
        action: OperatorActionRecord,
        child_confirmed_stopped: bool,
        cancellation_ref: str | None,
    ) -> FinalTruthRecord:
        residual = (
            ResidualUncertaintyClassification.NONE
            if child_confirmed_stopped
            else ResidualUncertaintyClassification.UNRESOLVED
        )
        return await publication.publish_final_truth(
                final_truth_record_id=f"agent-final-truth:{run.run_id}",
                run_id=run.run_id,
                result_class=ResultClass.BLOCKED,
                completion_classification=CompletionClassification.UNSATISFIED,
                evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
                residual_uncertainty_classification=residual,
                degradation_classification=DegradationClassification.NONE,
                closure_basis=ClosureBasisClassification.CANCELLED_BY_AUTHORITY,
                authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
                authoritative_result_ref=cancellation_ref or action.action_id,
        )
