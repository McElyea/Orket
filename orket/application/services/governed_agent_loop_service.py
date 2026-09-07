from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from orket.application.services.governed_agent_iteration_policy import (
    GovernedAgentVerificationObservation,
    agent_invocation_binding,
    agent_payload_digest,
    continuation_inputs,
)
from orket.application.services.governed_agent_ports import (
    GovernedAgentInvocationBinding,
    GovernedAgentIterationInvoker,
    GovernedAgentIterationRepository,
)
from orket.application.services.governed_agent_request_builder import (
    build_next_agent_iteration_request,
)
from orket.core.contracts import (
    AttemptRecord,
    FinalTruthRecord,
    RunRecord,
    StepRecord,
    WorkloadRecord,
)
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
    TerminalityBasisClassification,
)
from orket.core.domain.governed_agent_continuation import (
    GovernedAgentContinuationDecision,
    decide_governed_agent_continuation,
)
from orket_extension_sdk import AgentIterationRequest, AgentIterationResult


class GovernedAgentCompletionVerifier(Protocol):
    async def verify(
        self,
        *,
        request: AgentIterationRequest,
        result: AgentIterationResult,
    ) -> GovernedAgentVerificationObservation: ...


class GovernedAgentFinalTruthRepository(Protocol):
    async def save_final_truth(self, *, record: FinalTruthRecord) -> FinalTruthRecord: ...

    async def get_final_truth(self, *, run_id: str) -> FinalTruthRecord | None: ...


@dataclass(frozen=True, slots=True)
class GovernedAgentLoopExecution:
    run: RunRecord
    attempt: AttemptRecord
    decisions: tuple[GovernedAgentContinuationDecision, ...]
    invocation_ids: tuple[str, ...]
    final_truth: FinalTruthRecord | None
    normalized_reason: str | None


@dataclass(frozen=True, slots=True)
class _IterationExecution:
    result: AgentIterationResult | None
    decision: GovernedAgentContinuationDecision | None
    verification: GovernedAgentVerificationObservation | None
    failure: str | None


class GovernedAgentLoopService:
    """Application-owned bounded iteration progression over durable authority."""

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        iteration_repository: GovernedAgentIterationRepository,
        truth_repository: GovernedAgentFinalTruthRepository,
        invoker: GovernedAgentIterationInvoker,
        verifier: GovernedAgentCompletionVerifier,
    ) -> None:
        self._execution = execution_repository
        self._iterations = iteration_repository
        self._truth = truth_repository
        self._invoker = invoker
        self._verifier = verifier

    async def run_bounded(
        self,
        *,
        initial_request_payload: Mapping[str, Any],
        workload_record: WorkloadRecord,
        extension_digest: str,
        configuration_digest: str,
        admission_receipt_ref: str,
        creation_timestamp_utc: str,
        decision_timestamps_utc: Sequence[str],
        next_lease_expiries_utc: Sequence[str],
    ) -> GovernedAgentLoopExecution:
        request = AgentIterationRequest.from_wire(dict(initial_request_payload))
        run, attempt = await self._ensure_parent(
            request=request,
            workload_record=workload_record,
            configuration_digest=configuration_digest,
            admission_receipt_ref=admission_receipt_ref,
            creation_timestamp_utc=creation_timestamp_utc,
        )
        if run.final_truth_record_id is not None:
            truth = await self._truth.get_final_truth(run_id=run.run_id)
            return GovernedAgentLoopExecution(run, attempt, (), (), truth, None)
        if run.lifecycle_state is not RunState.EXECUTING:
            return GovernedAgentLoopExecution(run, attempt, (), (), None, "run_not_executing")
        maximum = request.remaining_run_budget.iterations
        if maximum < 1 or len(decision_timestamps_utc) < maximum:
            raise ValueError("E_AGENT_ITERATION_AUTHORIZATION_INPUT_MISSING")
        decisions: list[GovernedAgentContinuationDecision] = []
        invocation_ids: list[str] = []
        final_truth: FinalTruthRecord | None = None
        for index in range(maximum):
            binding = agent_invocation_binding(request, extension_digest)
            await self._ensure_step(binding)
            iteration = await self._execute_iteration(
                binding=binding,
                request=request,
                decision_timestamp_utc=decision_timestamps_utc[index],
            )
            invocation_ids.append(binding.invocation_id)
            if iteration.result is None or iteration.decision is None or iteration.verification is None:
                run = await self._execution.save_run_record(
                    record=run.model_copy(update={"lifecycle_state": RunState.RECOVERY_PENDING})
                )
                return GovernedAgentLoopExecution(run, attempt, tuple(decisions), tuple(invocation_ids), None, iteration.failure)
            result = iteration.result
            decision = iteration.decision
            verification = iteration.verification
            decisions.append(decision)
            if decision.disposition == "complete":
                run, attempt, final_truth = await self._close_verified_success(
                    run=run,
                    attempt=attempt,
                    verification=verification,
                    end_timestamp=decision_timestamps_utc[index],
                )
                break
            if not decision.next_iteration_authorized:
                run = await self._block_run(run, decision)
                return GovernedAgentLoopExecution(run, attempt, tuple(decisions), tuple(invocation_ids), None, decision.rule)
            if index + 1 >= maximum or index >= len(next_lease_expiries_utc):
                raise ValueError("E_AGENT_NEXT_ITERATION_AUTHORIZATION_MISSING")
            request = build_next_agent_iteration_request(
                current_request=request,
                accepted_result=result,
                next_lease_expires_at_utc=next_lease_expiries_utc[index],
                verification_evidence_ref=verification.evidence_ref,
            )
        return GovernedAgentLoopExecution(run, attempt, tuple(decisions), tuple(invocation_ids), final_truth, None)

    async def _ensure_parent(
        self,
        *,
        request: AgentIterationRequest,
        workload_record: WorkloadRecord,
        configuration_digest: str,
        admission_receipt_ref: str,
        creation_timestamp_utc: str,
    ) -> tuple[RunRecord, AttemptRecord]:
        identity = request.identity
        run = RunRecord(
            run_id=identity.run_id,
            workload_id=workload_record.workload_id,
            workload_version=workload_record.workload_version,
            policy_snapshot_id=request.policy_ref,
            policy_digest=request.policy_digest,
            configuration_snapshot_id=f"agent-config:{identity.run_id}",
            configuration_digest=configuration_digest,
            creation_timestamp=creation_timestamp_utc,
            admission_decision_receipt_ref=admission_receipt_ref,
            namespace_scope=request.namespace_scope[0] if len(request.namespace_scope) == 1 else None,
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=identity.attempt_id,
        )
        attempt = AttemptRecord(
            attempt_id=identity.attempt_id,
            run_id=identity.run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref=f"agent-state:{identity.run_id}:initial",
            start_timestamp=creation_timestamp_utc,
        )
        existing_run = await self._execution.get_run_record(run_id=run.run_id)
        existing_attempt = await self._execution.get_attempt_record(attempt_id=attempt.attempt_id)
        if existing_run is not None and not _same_run_authority(existing_run, run):
            raise ValueError("E_AGENT_RUN_ID_CONFLICT")
        if existing_attempt is not None and (
            existing_attempt.run_id != attempt.run_id
            or existing_attempt.attempt_ordinal != attempt.attempt_ordinal
        ):
            raise ValueError("E_AGENT_ATTEMPT_ID_CONFLICT")
        if existing_run is None:
            existing_run = await self._execution.save_run_record(record=run)
        if existing_attempt is None:
            existing_attempt = await self._execution.save_attempt_record(record=attempt)
        return existing_run, existing_attempt

    async def _ensure_step(self, binding: GovernedAgentInvocationBinding) -> StepRecord:
        step = StepRecord(
            step_id=binding.step_id,
            attempt_id=binding.attempt_id,
            step_kind="governed_agent_iteration",
            input_ref=binding.request_digest,
            observed_result_classification="dispatch_prepared",
            closure_classification="step_open",
        )
        existing = await self._execution.get_step_record(step_id=binding.step_id)
        if existing is not None:
            if existing.input_ref != binding.request_digest or existing.attempt_id != binding.attempt_id:
                raise ValueError("E_AGENT_STEP_ID_CONFLICT")
            return existing
        return await self._execution.save_step_record(record=step)

    async def _execute_iteration(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        request: AgentIterationRequest,
        decision_timestamp_utc: str,
    ) -> _IterationExecution:
        result, failure = await self._invoke_and_accept(binding, request)
        if result is None:
            return _IterationExecution(None, None, None, failure)
        verification = await self._verifier.verify(request=request, result=result)
        inputs = continuation_inputs(
            request=request,
            result=result,
            verification=verification,
            decision_timestamp_utc=decision_timestamp_utc,
        )
        decision = decide_governed_agent_continuation(inputs)
        publication = await self._iterations.publish_continuation_decision(
            binding=binding,
            accepted_result_digest=agent_payload_digest(result.to_wire()),
            decision_inputs=inputs.to_payload(),
            decision_payload=decision.to_payload(),
        )
        if publication.status not in {"accepted", "idempotent"}:
            raise ValueError(f"E_AGENT_DECISION_PUBLICATION_{publication.status.upper()}")
        await self._close_step(binding, verification, publication.durable_decision_ref)
        return _IterationExecution(result, decision, verification, None)

    async def _invoke_and_accept(
        self,
        binding: GovernedAgentInvocationBinding,
        request: AgentIterationRequest,
    ) -> tuple[AgentIterationResult | None, str | None]:
        preparation = await self._iterations.prepare_dispatch(binding=binding, request_payload=request.to_wire())
        if preparation.status != "prepared":
            return await self._recover_recorded_result(binding, preparation.status)
        outcome = await self._invoker.invoke_once(binding=binding, request_payload=request.to_wire())
        if outcome.status != "returned" or outcome.result_payload is None:
            await self._iterations.record_interrupted_publication(
                binding=binding,
                normalized_reason=str(outcome.normalized_reason or outcome.status),
                provider_or_effect_uncertain=outcome.status in {"timed_out", "protocol_failed"},
            )
            return None, str(outcome.normalized_reason or outcome.status)
        acceptance = await self._iterations.accept_result(outcome=outcome)
        if acceptance.status not in {"accepted", "idempotent"}:
            return None, f"result_{acceptance.status}"
        return AgentIterationResult.from_wire(dict(outcome.result_payload)), None

    async def _recover_recorded_result(
        self,
        binding: GovernedAgentInvocationBinding,
        preparation_status: str,
    ) -> tuple[AgentIterationResult | None, str | None]:
        if preparation_status != "idempotent":
            return None, f"dispatch_{preparation_status}"
        snapshot = await self._iterations.get_iteration_snapshot(invocation_id=binding.invocation_id)
        if snapshot is None or snapshot.result_payload is None:
            await self._iterations.record_interrupted_publication(
                binding=binding,
                normalized_reason="restart_after_dispatch_requires_recovery",
                provider_or_effect_uncertain=True,
            )
            return None, "restart_after_dispatch_requires_recovery"
        return AgentIterationResult.from_wire(dict(snapshot.result_payload)), None

    async def _close_step(
        self,
        binding: GovernedAgentInvocationBinding,
        verification: GovernedAgentVerificationObservation,
        decision_ref: str | None,
    ) -> None:
        step = await self._execution.get_step_record(step_id=binding.step_id)
        if step is None:
            raise ValueError("E_AGENT_STEP_MISSING")
        receipts = [verification.evidence_ref]
        if decision_ref is not None:
            receipts.append(decision_ref)
        await self._execution.save_step_record(
            record=step.model_copy(
                update={
                    "output_ref": f"agent-result:{binding.invocation_id}",
                    "observed_result_classification": "agent_result_accepted",
                    "receipt_refs": receipts,
                    "closure_classification": "step_completed",
                }
            )
        )

    async def _close_verified_success(
        self,
        *,
        run: RunRecord,
        attempt: AttemptRecord,
        verification: GovernedAgentVerificationObservation,
        end_timestamp: str,
    ) -> tuple[RunRecord, AttemptRecord, FinalTruthRecord]:
        truth = await self._truth.save_final_truth(
            record=FinalTruthRecord(
                final_truth_record_id=f"agent-final-truth:{run.run_id}",
                run_id=run.run_id,
                result_class=ResultClass.SUCCESS,
                completion_classification=CompletionClassification.SATISFIED,
                evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
                residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
                degradation_classification=DegradationClassification.NONE,
                closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
                terminality_basis=TerminalityBasisClassification.COMPLETED_TERMINAL,
                authority_sources=[AuthoritySourceClass.VALIDATED_ARTIFACT],
                authoritative_result_ref=verification.authoritative_result_ref,
            )
        )
        closed_attempt = await self._execution.save_attempt_record(
            record=attempt.model_copy(
                update={"attempt_state": AttemptState.COMPLETED, "end_timestamp": end_timestamp}
            )
        )
        closed_run = await self._execution.save_run_record(
            record=run.model_copy(
                update={"lifecycle_state": RunState.COMPLETED, "final_truth_record_id": truth.final_truth_record_id}
            )
        )
        return closed_run, closed_attempt, truth

    async def _block_run(
        self,
        run: RunRecord,
        decision: GovernedAgentContinuationDecision,
    ) -> RunRecord:
        state = RunState.RECOVERY_PENDING if decision.disposition == "recover" else RunState.OPERATOR_BLOCKED
        return await self._execution.save_run_record(record=run.model_copy(update={"lifecycle_state": state}))


def _same_run_authority(existing: RunRecord, expected: RunRecord) -> bool:
    return cast(
        bool,
        existing.run_id == expected.run_id
        and existing.workload_id == expected.workload_id
        and existing.workload_version == expected.workload_version
        and existing.policy_snapshot_id == expected.policy_snapshot_id
        and existing.policy_digest == expected.policy_digest
        and existing.configuration_snapshot_id == expected.configuration_snapshot_id
        and existing.configuration_digest == expected.configuration_digest
        and existing.admission_decision_receipt_ref == expected.admission_decision_receipt_ref
        and existing.namespace_scope == expected.namespace_scope
        and existing.current_attempt_id == expected.current_attempt_id,
    )
