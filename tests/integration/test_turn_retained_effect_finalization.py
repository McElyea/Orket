"""Durable attempt evidence owns the terminal side-effect boundary."""
from __future__ import annotations

from pathlib import Path

import pytest

from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.core.contracts.turn_tool_dispatch import is_unresolved_tool_dispatch
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    ClosureBasisClassification,
    RecoveryActionClass,
    ResultClass,
    RunState,
    SideEffectBoundaryClass,
)
from tests.helpers.governed_operation_binding import seed_open_cache
from tests.helpers.operation_binding import (
    ARGS,
    ATTEMPT_ID,
    ISSUE,
    ROLE,
    RUN_ID,
    SESSION,
    TURN,
    make_case,
    operation_id,
    proposal,
)
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]

RESULT_REF = f"turn-tool-violations:{RUN_ID}"
VIOLATIONS = ["E_OPERATION_ARTIFACT_INVALID:result_digest_mismatch"]


async def _begin(case):  # type: ignore[no-untyped-def]
    return await case.service.begin_execution(
        session_id=SESSION,
        issue_id=ISSUE,
        role_name=ROLE,
        turn_index=TURN,
        proposal_hash="durable-boundary-proposal",
    )


async def _decision(case, attempt):  # type: ignore[no-untyped-def]
    assert attempt.recovery_decision_id is not None
    decision = await case.service.publication.repository.get_recovery_decision(
        decision_id=attempt.recovery_decision_id
    )
    assert decision is not None
    return decision


def _dump(record):  # type: ignore[no-untyped-def]
    return record.model_dump(mode="json")


# Layer: integration
async def test_retained_same_attempt_effect_overrides_invocation_local_zero(tmp_path: Path) -> None:
    case = make_case(tmp_path, [proposal()])
    seeded = await seed_open_cache(case, anchor="coherent")
    step_before = await case.service.execution_repository.get_step_record(step_id=operation_id())
    effects_before = await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID)
    calls_before = case.toolbox.calls

    run, attempt, truth = await case.service.finalize_execution(
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
        authoritative_result_ref=RESULT_REF,
        violation_reasons=VIOLATIONS,
        executed_step_count=0,
    )
    decision = await _decision(case, attempt)
    step_after = await case.service.execution_repository.get_step_record(step_id=operation_id())
    effects_after = await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID)
    journal_ref = f"turn-tool-journal:{operation_id()}"
    observed_result_ref = f"turn-tool-result:{operation_id()}"

    assert seeded.attempt.attempt_id == ATTEMPT_ID
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert attempt.failure_class == "tool_execution_failed"
    assert decision.failed_attempt_id == ATTEMPT_ID
    assert decision.failure_classification_basis == "tool_execution_failed"
    assert decision.side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.rationale_ref == journal_ref
    assert decision.required_precondition_refs == [RESULT_REF, journal_ref, observed_result_ref]
    assert truth.result_class is ResultClass.FAILED
    assert truth.closure_basis is ClosureBasisClassification.NORMAL_EXECUTION
    assert truth.authority_sources == [
        AuthoritySourceClass.RECEIPT_EVIDENCE,
        AuthoritySourceClass.VALIDATED_ARTIFACT,
    ]
    assert truth.authoritative_result_ref == RESULT_REF
    assert step_before is not None and step_after is not None
    assert _dump(step_after) == _dump(step_before)
    assert [_dump(effect) for effect in effects_after] == [_dump(effect) for effect in effects_before]
    assert case.toolbox.calls == calls_before == 1


# Layer: integration
async def test_empty_attempt_retains_true_pre_effect_terminal_classification(tmp_path: Path) -> None:
    case = make_case(tmp_path, [proposal()])
    run, opening_attempt = await _begin(case)
    assert await case.service.execution_repository.list_step_records(attempt_id=ATTEMPT_ID) == []
    assert await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID) == []

    run, attempt, truth = await case.service.finalize_execution(
        run_id=run.run_id,
        attempt_id=opening_attempt.attempt_id,
        authoritative_result_ref=RESULT_REF,
        violation_reasons=VIOLATIONS,
        executed_step_count=0,
    )
    decision = await _decision(case, attempt)

    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert attempt.failure_class == "tool_execution_blocked"
    assert decision.failed_attempt_id == ATTEMPT_ID
    assert decision.failure_classification_basis == "tool_execution_blocked"
    assert decision.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.rationale_ref == RESULT_REF
    assert decision.required_precondition_refs == [RESULT_REF]
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.POLICY_TERMINAL_STOP
    assert truth.authority_sources == [AuthoritySourceClass.RECEIPT_EVIDENCE]
    assert truth.authoritative_result_ref == RESULT_REF
    assert await case.service.execution_repository.list_step_records(attempt_id=ATTEMPT_ID) == []
    assert await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID) == []
    assert case.toolbox.calls == 0


# Layer: integration
async def test_unresolved_dispatch_still_refuses_terminal_classification(tmp_path: Path) -> None:
    case = make_case(tmp_path, [proposal()])
    run, attempt = await _begin(case)
    step = await case.service.prepare_dispatch(
        run_id=run.run_id,
        attempt_id=attempt.attempt_id,
        step_id=operation_id(),
        tool_name="write_file",
        tool_args=ARGS,
        binding=None,
        operation_id=operation_id(),
    )
    run_before = await case.service.execution_repository.get_run_record(run_id=RUN_ID)
    attempt_before = await case.service.execution_repository.get_attempt_record(attempt_id=ATTEMPT_ID)
    effects_before = await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID)
    assert is_unresolved_tool_dispatch(step)
    assert run_before is not None and attempt_before is not None and effects_before == []

    with pytest.raises(TurnToolControlPlaneError, match="tool dispatch outcome unknown"):
        await case.service.finalize_execution(
            run_id=run.run_id,
            attempt_id=attempt.attempt_id,
            authoritative_result_ref=RESULT_REF,
            violation_reasons=VIOLATIONS,
            executed_step_count=0,
        )

    run_after = await case.service.execution_repository.get_run_record(run_id=RUN_ID)
    attempt_after = await case.service.execution_repository.get_attempt_record(attempt_id=ATTEMPT_ID)
    step_after = await case.service.execution_repository.get_step_record(step_id=operation_id())
    effects_after = await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID)
    truth = await case.service.publication.repository.get_final_truth(run_id=RUN_ID)

    assert run_after is not None and attempt_after is not None and step_after is not None
    assert _dump(run_after) == _dump(run_before)
    assert _dump(attempt_after) == _dump(attempt_before)
    assert _dump(step_after) == _dump(step)
    assert is_unresolved_tool_dispatch(step_after)
    assert effects_after == effects_before == []
    assert truth is None
    assert attempt_after.recovery_decision_id is None
    assert run_after.lifecycle_state is RunState.EXECUTING
    assert attempt_after.attempt_state is AttemptState.EXECUTING
    assert case.toolbox.calls == 0
