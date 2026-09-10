from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from orket.application.services.governed_agent_context_plan import (
    bind_continuation_configuration,
    same_run_authority,
    validate_continuation_inputs,
)
from orket.application.services.governed_agent_iteration_policy import (
    GovernedAgentVerificationObservation,
    agent_invocation_binding,
    agent_payload_digest,
    continuation_inputs,
)
from orket.application.services.governed_agent_ports import (
    GovernedAgentAuthorityGuard,
    GovernedAgentInvocationBinding,
    GovernedAgentIterationInvoker,
    GovernedAgentIterationRepository,
)
from orket.application.services.governed_agent_progress_policy import with_recorded_progress
from orket.application.services.governed_agent_request_builder import (
    build_next_agent_iteration_request,
)
from orket.application.services.governed_agent_run_control_service import (
    GovernedAgentRunControlRepository,
    with_operator_controls,
)
from orket.application.services.governed_agent_terminal_service import (
    GovernedAgentFinalTruthRepository,
    close_agent_run,
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
    RunState,
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
        authority_guard: GovernedAgentAuthorityGuard | None = None,
        run_controls: GovernedAgentRunControlRepository | None = None,
    ) -> None:
        self._execution = execution_repository
        self._iterations = iteration_repository
        self._truth = truth_repository
        self._invoker = invoker
        self._verifier = verifier
        self._authority_guard = authority_guard
        self._run_controls = run_controls

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
        continuation_inputs_payload: Mapping[str, Any] | None = None,
    ) -> GovernedAgentLoopExecution:
        request = AgentIterationRequest.from_wire(dict(initial_request_payload))
        context_plan = validate_continuation_inputs(request, continuation_inputs_payload)
        configuration_digest = bind_continuation_configuration(configuration_digest, context_plan)
        await self._ensure_authority()
        run, attempt = await self._ensure_parent(
            request=request, workload_record=workload_record,
            configuration_digest=configuration_digest, admission_receipt_ref=admission_receipt_ref,
            creation_timestamp_utc=creation_timestamp_utc,
        )
        if run.final_truth_record_id is not None:
            await self._ensure_authority()
            truth = await self._truth.get_final_truth(run_id=run.run_id)
            return GovernedAgentLoopExecution(run, attempt, (), (), truth, None)
        if run.lifecycle_state is not RunState.EXECUTING:
            return GovernedAgentLoopExecution(run, attempt, (), (), None, "run_not_executing")
        if (maximum := request.remaining_run_budget.iterations) < 1 or len(decision_timestamps_utc) < maximum:
            raise ValueError("E_AGENT_ITERATION_AUTHORIZATION_INPUT_MISSING")
        decisions: list[GovernedAgentContinuationDecision] = []
        invocation_ids: list[str] = []
        final_truth: FinalTruthRecord | None = None
        for index in range(maximum):
            await self._ensure_authority()
            binding = agent_invocation_binding(request, extension_digest)
            await self._ensure_step(binding)
            iteration = await self._execute_iteration(
                binding=binding,
                request=request,
                decision_timestamp_utc=decision_timestamps_utc[index],
            )
            invocation_ids.append(binding.invocation_id)
            if iteration.result is None or iteration.decision is None or iteration.verification is None:
                await self._ensure_authority()
                run = await self._execution.save_run_record(
                    record=run.model_copy(update={"lifecycle_state": RunState.RECOVERY_PENDING})
                )
                return GovernedAgentLoopExecution(run, attempt, tuple(decisions), tuple(invocation_ids), None, iteration.failure)
            result = iteration.result
            decision = iteration.decision
            verification = iteration.verification
            decisions.append(decision)
            if decision.disposition in {"complete", "blocked", "failed"}:
                run, attempt, final_truth = await close_agent_run(
                    execution=self._execution, truth_repository=self._truth, guard=self._authority_guard,
                    decision=decision, decision_ref=f"agent-decision:{binding.invocation_id}",
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
                next_context_inputs=context_plan.get(str(request.identity.iteration_ordinal + 1)),
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
        if existing_run is not None and not same_run_authority(existing_run, run):
            raise ValueError("E_AGENT_RUN_ID_CONFLICT")
        if existing_attempt is not None and (
            existing_attempt.run_id != attempt.run_id
            or existing_attempt.attempt_ordinal != attempt.attempt_ordinal
        ):
            raise ValueError("E_AGENT_ATTEMPT_ID_CONFLICT")
        if existing_run is None:
            await self._ensure_authority()
            existing_run = await self._execution.save_run_record(record=run)
        if existing_attempt is None:
            await self._ensure_authority()
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
        await self._ensure_authority()
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
        inputs = with_recorded_progress(inputs, request, verification,
                                       await self._iterations.list_iteration_snapshots(run_id=binding.run_id))
        # At most one pause and one stop can race this boundary; every retry rereads durable authority.
        for _ in range(3):
            inputs = await with_operator_controls(inputs, self._run_controls, binding.invocation_id)
            decision = decide_governed_agent_continuation(inputs)
            await self._ensure_authority()
            publication = await self._iterations.publish_continuation_decision(
                binding=binding, accepted_result_digest=agent_payload_digest(result.to_wire()),
                decision_inputs=inputs.to_payload(), decision_payload=decision.to_payload(),
            )
            if publication.status != "control_changed":
                break
        if publication.status not in {"accepted", "idempotent"}:
            raise ValueError(f"E_AGENT_DECISION_PUBLICATION_{publication.status.upper()}")
        await self._close_step(binding, verification, publication.durable_decision_ref)
        return _IterationExecution(result, decision, verification, None)

    async def _invoke_and_accept(
        self,
        binding: GovernedAgentInvocationBinding,
        request: AgentIterationRequest,
    ) -> tuple[AgentIterationResult | None, str | None]:
        await self._ensure_authority()
        preparation = await self._iterations.prepare_dispatch(binding=binding, request_payload=request.to_wire())
        if preparation.status != "prepared":
            return await self._recover_recorded_result(binding, preparation.status)
        await self._ensure_authority()
        outcome = await self._invoker.invoke_once(binding=binding, request_payload=request.to_wire())
        await self._ensure_authority()
        if outcome.status != "returned" or outcome.result_payload is None:
            await self._iterations.record_interrupted_publication(
                binding=binding,
                normalized_reason=str(outcome.normalized_reason or outcome.status),
                provider_or_effect_uncertain=outcome.status in {"timed_out", "protocol_failed"},
            )
            return None, str(outcome.normalized_reason or outcome.status)
        await self._ensure_authority()
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
        await self._ensure_authority()
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

    async def _block_run(
        self,
        run: RunRecord,
        decision: GovernedAgentContinuationDecision,
    ) -> RunRecord:
        state = RunState.RECOVERY_PENDING if decision.disposition == "recover" else RunState.OPERATOR_BLOCKED
        await self._ensure_authority()
        return await self._execution.save_run_record(record=run.model_copy(update={"lifecycle_state": state}))

    async def _ensure_authority(self) -> None:
        if self._authority_guard is not None:
            await self._authority_guard.ensure_active()
