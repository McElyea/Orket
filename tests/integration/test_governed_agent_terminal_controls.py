"""Operator terminal outcomes retain one complete authority transition."""
from __future__ import annotations

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.async_pending_gate_repository import AsyncPendingGateRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.application.services.governed_agent_commands import UnownedGovernedAgentInvoker
from orket.application.services.governed_agent_operator_service import GovernedAgentOperatorService
from orket.core.domain import AttemptState, ResidualUncertaintyClassification, RunState
from tests.integration.test_governed_agent_effect_service import _proposal, _setup
from tests.runtime.governed_agent_test_support import binding_for

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
FAULT = "agent-terminal-control-write-interrupted"


async def terminal_control(tmp_path, operation):
    request, effects, execution, records = await _setup(tmp_path)
    if operation == "deny":
        proposal = _proposal(request, "terminal-denial", "write_file", "reports/denied.json", {"refused": True})
        pending = await effects.prepare(request=request, proposal=proposal, created_at="2026-09-14T01:00:00Z")

        async def invoke():
            return await effects.resolve_write(approval_id=pending.approval_id, decision="denied",
                actor_ref="operator:terminal-test", timestamp="2026-09-14T01:00:01Z")
    else:
        if operation == "cancel-unobserved":
            payload = request.to_wire()
            binding = binding_for(payload)
            run = await execution.get_run_record(run_id=request.identity.run_id)
            await execution.save_run_record(record=run.model_copy(update={"lifecycle_state": RunState.EXECUTING}))
            step = await execution.get_step_record(step_id=request.identity.step_id)
            assert step.input_ref == binding.request_digest
            await execution.save_step_record(record=step.model_copy(update={
                "observed_result_classification": "dispatch_prepared",
            }))
            prepared = await AsyncGovernedAgentRepository(execution.db_path).prepare_dispatch(binding=binding, request_payload=payload)
            assert prepared.status == "prepared"
        operator = GovernedAgentOperatorService(
            transactions=SQLiteControlPlaneTransactions(execution.db_path),
            iteration_repository=AsyncGovernedAgentRepository(execution.db_path),
            invoker=UnownedGovernedAgentInvoker(),
        )

        async def invoke():
            return await operator.cancel_run(run_id=request.identity.run_id, action_id="cancel:terminal-test",
                actor_ref="operator:terminal-test", timestamp_utc="2026-09-14T01:00:01Z", reason="operator_request",
                cancellation_epoch=1, grace_period_seconds=0)
    return request, execution, records, invoke


@pytest.mark.parametrize("operation", ["deny", "cancel", "cancel-unobserved"])
@pytest.mark.parametrize("interrupt", [None, "attempt", "run"])
# Layer: integration
async def test_terminal_control_is_atomic_and_retry_finishes_retained_outcome(tmp_path, monkeypatch, operation, interrupt):
    request, execution, records, invoke = await terminal_control(tmp_path, operation)
    before_run = await execution.get_run_record(run_id=request.identity.run_id)
    before_attempt = await execution.get_attempt_record(attempt_id=request.identity.attempt_id)
    pending = AsyncPendingGateRepository(execution.db_path)
    before_pending = await pending.list_requests()
    hits = []
    original_attempt = AsyncControlPlaneExecutionRepository.save_attempt_record
    original_run = AsyncControlPlaneExecutionRepository.save_run_record

    async def save_attempt(repository, *, record):
        if interrupt == "attempt" and record.attempt_state in {AttemptState.FAILED, AttemptState.INTERRUPTED}:
            hits.append(record.attempt_id)
            raise RuntimeError(FAULT)
        return await original_attempt(repository, record=record)

    async def save_run(repository, *, record):
        if interrupt == "run" and record.lifecycle_state in {RunState.FAILED_TERMINAL, RunState.CANCELLED}:
            hits.append(record.run_id)
            raise RuntimeError(FAULT)
        return await original_run(repository, record=record)

    with monkeypatch.context() as patch:
        patch.setattr(AsyncControlPlaneExecutionRepository, "save_attempt_record", save_attempt)
        patch.setattr(AsyncControlPlaneExecutionRepository, "save_run_record", save_run)
        if interrupt:
            with pytest.raises(RuntimeError, match=FAULT):
                await invoke()
            assert hits
            assert await records.get_final_truth(run_id=request.identity.run_id) is None
            assert await execution.get_run_record(run_id=request.identity.run_id) == before_run
            assert await execution.get_attempt_record(attempt_id=request.identity.attempt_id) == before_attempt
            if operation == "deny":
                assert await pending.list_requests() == before_pending
                assert await records.list_operator_actions(target_ref=request.identity.run_id) == []
        else:
            await invoke()
    if interrupt:
        await invoke()
    truth = await records.get_final_truth(run_id=request.identity.run_id)
    run = await execution.get_run_record(run_id=request.identity.run_id)
    attempt = await execution.get_attempt_record(attempt_id=request.identity.attempt_id)
    assert truth is not None and truth.result_class.value == "blocked"
    expected = ResidualUncertaintyClassification.UNRESOLVED if operation == "cancel-unobserved" else ResidualUncertaintyClassification.NONE
    assert truth.residual_uncertainty_classification is expected
    assert run.final_truth_record_id == truth.final_truth_record_id
    assert run.lifecycle_state is (RunState.FAILED_TERMINAL if operation == "deny" else RunState.CANCELLED)
    assert attempt.end_timestamp == "2026-09-14T01:00:01Z"
    assert not (tmp_path / "reports/denied.json").exists()
