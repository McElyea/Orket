"""Binding controls for ordinary governed operation-cache reuse."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orket.application.services.turn_tool_control_plane_resource_lifecycle import lease_id_for_run
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.application.workflows.turn_executor import ToolValidationError
from orket.core.domain import (
    AttemptState,
    ClosureBasisClassification,
    LeaseStatus,
    RecoveryActionClass,
    ReservationStatus,
    ResultClass,
    RunState,
    SideEffectBoundaryClass,
)
from tests.helpers.governed_operation_binding import seed_open_cache
from tests.helpers.operation_binding import (
    ARGS,
    ATTEMPT_ID,
    RUN_ID,
    context,
    control_plane_state,
    dispatch,
    file_bytes,
    immutable_physical,
    legacy_result_physical,
    make_case,
    mutate_record,
    operation_record,
    proposal,
    write_legacy_result,
    write_operation,
)
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]


async def _attempt(case, proposed, *, resume: bool = False):  # type: ignore[no-untyped-def]
    try:
        return await dispatch(case, proposed, resume=resume), None
    except (ToolValidationError, TurnToolControlPlaneError, RuntimeError, ValueError) as error:
        return None, error


def _record(record_property, **payload):  # type: ignore[no-untyped-def]
    record_property("governed_operation_cache_observation", json.dumps(payload, sort_keys=True))


def _terminal_failure_expectations(attempt_effects):  # type: ignore[no-untyped-def]
    if attempt_effects:
        return (SideEffectBoundaryClass.POST_EFFECT_OBSERVED, ResultClass.FAILED,
                ClosureBasisClassification.NORMAL_EXECUTION, "tool_execution_failed")
    return (SideEffectBoundaryClass.PRE_EFFECT_FAILURE, ResultClass.BLOCKED,
            ClosureBasisClassification.POLICY_TERMINAL_STOP, "tool_execution_blocked")


def _assert_rejected_call_finalized(before_state, after_state, before_files, after_files) -> None:
    before_attempt = next(
        (row for row in before_state["attempts"] if row["attempt_id"] == ATTEMPT_ID), None
    )
    after_attempt = next(row for row in after_state["attempts"] if row["attempt_id"] == ATTEMPT_ID)
    other_before = [row for row in before_state["attempts"] if row["attempt_id"] != ATTEMPT_ID]
    other_after = [row for row in after_state["attempts"] if row["attempt_id"] != ATTEMPT_ID]
    truth = after_state["truth"]
    decision = after_state["decision"]
    attempt_effects = [row for row in before_state["effects"] if row["attempt_id"] == ATTEMPT_ID]
    boundary, result_class, closure_basis, failure_class = _terminal_failure_expectations(attempt_effects)
    expected_rationale_ref = (
        attempt_effects[-1]["journal_entry_id"]
        if attempt_effects else f"turn-tool-violations:{RUN_ID}"
    )

    if before_state["run"] is None:
        assert before_state["attempts"] == [] and before_state["truth"] is None
        assert before_state["decision"] is None
        assert before_state["reservation"] is None and before_state["lease"] is None
    else:
        assert before_state["run"]["lifecycle_state"] == RunState.EXECUTING.value
        assert before_attempt is not None
        assert before_attempt["attempt_state"] == AttemptState.EXECUTING.value
    assert after_state["run"]["lifecycle_state"] == RunState.FAILED_TERMINAL.value
    assert after_attempt["attempt_state"] == AttemptState.FAILED.value
    assert after_attempt["side_effect_boundary_class"] == boundary.value
    assert after_attempt["failure_class"] == failure_class
    assert before_state["truth"] is None and truth["result_class"] == result_class.value
    assert truth["closure_basis"] == closure_basis.value
    assert truth["authoritative_result_ref"] == f"turn-tool-violations:{RUN_ID}"
    assert after_state["run"]["final_truth_record_id"] == truth["final_truth_record_id"]
    assert after_attempt["recovery_decision_id"] == decision["decision_id"]
    assert decision["failure_classification_basis"] == failure_class
    assert decision["authorized_next_action"] == RecoveryActionClass.TERMINATE_RUN.value
    assert decision["side_effect_boundary_class"] == boundary.value
    assert decision["rationale_ref"] == expected_rationale_ref
    assert truth["authoritative_result_ref"] in decision["required_precondition_refs"]
    assert expected_rationale_ref in decision["required_precondition_refs"]
    assert RecoveryActionClass.RESUME_FROM_CHECKPOINT.value in decision["blocked_actions"]
    assert other_after == other_before
    assert after_state["step"] == before_state["step"]
    assert after_state["effects"] == before_state["effects"]
    assert after_state["checkpoint"] == before_state["checkpoint"]
    if before_state["reservation"] is not None:
        assert after_state["reservation"] == before_state["reservation"]
        assert before_state["reservation"]["status"] == ReservationStatus.PROMOTED_TO_LEASE.value
        assert before_state["lease"] is not None
        assert before_state["lease"]["status"] == LeaseStatus.ACTIVE.value
        assert before_state["lease"]["lease_id"] == after_state["lease"]["lease_id"]
    assert after_state["reservation"]["status"] == ReservationStatus.PROMOTED_TO_LEASE.value
    assert after_state["lease"]["status"] == LeaseStatus.RELEASED.value
    assert after_state["lease"]["lease_id"] == lease_id_for_run(run_id=RUN_ID)
    for name in ("operation", "receipt", "effect"):
        assert after_files[name] == before_files[name]
    assert any(after_files[name] != before_files[name]
        for name in ("control_plane", "control_plane_wal", "control_plane_shm"))


# Layer: integration
async def test_governed_operation_cache_reuses_exact_record_with_coherent_current_attempt_anchor(
    tmp_path: Path, record_property,
) -> None:
    case = make_case(tmp_path, [proposal()])
    seeded = await seed_open_cache(case, anchor="coherent")
    before_state = await control_plane_state(case)
    before_files = await immutable_physical(case)
    receipt_before = await file_bytes(case, "receipt")
    operation_before = await file_bytes(case, "operation")

    turn, error = await _attempt(case, proposal())
    after_state = await control_plane_state(case)
    after_files = await immutable_physical(case)
    receipt_after = await file_bytes(case, "receipt")
    operation_after = await file_bytes(case, "operation")
    _record(record_property, error=None if error is None else str(error),
        before_state=before_state, after_state=after_state,
        before_files=before_files, after_files=after_files)

    assert error is None and turn is not None
    assert turn.tool_calls[0].result == seeded.result
    assert case.toolbox.calls == 1 and len(case.probe.calls) == 1
    assert operation_after == operation_before
    assert receipt_after is not None and receipt_after.startswith(receipt_before or b"")
    assert after_state["step"] == before_state["step"]
    assert after_state["effects"] == before_state["effects"]
    assert after_state["run"]["lifecycle_state"] == "completed"


# Layer: integration
async def test_governed_legacy_resume_cache_refuses_without_current_attempt_anchor(
    tmp_path: Path, record_property,
) -> None:
    case = make_case(tmp_path, [proposal()])
    seeded_result = await case.toolbox.execute("write_file", ARGS, context())
    await write_legacy_result(case, args=ARGS, result=seeded_result)
    before_state = await control_plane_state(case)
    before_files = await immutable_physical(case)
    legacy_before = await legacy_result_physical(case, ARGS)
    before_toolbox, before_hooks = case.toolbox.calls, len(case.probe.calls)

    turn, error = await _attempt(case, proposal(), resume=True)
    after_state = await control_plane_state(case)
    after_files = await immutable_physical(case)
    legacy_after = await legacy_result_physical(case, ARGS)
    _record(record_property, anchor="absent", turn_present=turn is not None,
        error=None if error is None else str(error), before_state=before_state,
        after_state=after_state, before_files=before_files, after_files=after_files,
        legacy_before=legacy_before, legacy_after=legacy_after)

    assert legacy_before is not None and legacy_after == legacy_before
    assert turn is None and error is not None
    assert "E_OPERATION_ARTIFACT_INVALID:control_plane_anchor_missing" in str(error)
    assert case.toolbox.calls == before_toolbox and len(case.probe.calls) == before_hooks
    _assert_rejected_call_finalized(before_state, after_state, before_files, after_files)


@pytest.mark.parametrize(
    ("mutation", "reason", "stored_args", "proposed_args"),
    [
        pytest.param("operation_id", "operation_id_mismatch", ARGS, ARGS, id="operation-id"),
        pytest.param("tool", "tool_mismatch", ARGS, ARGS, id="tool"),
        pytest.param("args", "args_mismatch", ARGS, ARGS, id="args"),
        pytest.param("result", "result_digest_mismatch", ARGS, ARGS, id="result-only"),
        pytest.param("digest", "result_digest_mismatch", ARGS, ARGS, id="digest-only"),
        pytest.param("missing_digest", "malformed", ARGS, ARGS, id="missing-digest"),
        pytest.param("malformed_digest", "malformed", ARGS, ARGS, id="malformed-digest"),
        pytest.param(None, "args_mismatch", {**ARGS, "mode": True}, {**ARGS, "mode": 1},
            id="bool-int-args"),
    ],
)
# Layer: integration
async def test_governed_operation_cache_refuses_present_invalid_record_before_publication(
    tmp_path: Path,
    record_property,
    mutation: str | None,
    reason: str,
    stored_args: dict[str, Any],
    proposed_args: dict[str, Any],
) -> None:
    case = make_case(tmp_path, [proposal(args=proposed_args)])
    await seed_open_cache(case, anchor="coherent", stored_args=stored_args)
    stored = await operation_record(case)
    assert stored is not None
    if mutation is not None:
        await write_operation(case, mutate_record(stored, mutation))
    before_state = await control_plane_state(case)
    before_files = await immutable_physical(case)
    before_toolbox, before_hooks = case.toolbox.calls, len(case.probe.calls)

    turn, error = await _attempt(case, proposal(args=proposed_args))
    after_state = await control_plane_state(case)
    after_files = await immutable_physical(case)
    _record(record_property, mutation=mutation, reason=reason, turn_present=turn is not None,
        error=None if error is None else str(error), before_state=before_state, after_state=after_state,
        before_files=before_files, after_files=after_files)

    assert turn is None and error is not None
    assert f"E_OPERATION_ARTIFACT_INVALID:{reason}" in str(error)
    assert case.toolbox.calls == before_toolbox and len(case.probe.calls) == before_hooks
    _assert_rejected_call_finalized(before_state, after_state, before_files, after_files)


@pytest.mark.parametrize(
    ("anchor", "reason"),
    [
        pytest.param("absent", "control_plane_anchor_missing", id="absent"),
        pytest.param("mismatch", "control_plane_anchor_mismatch", id="call-mismatch"),
        pytest.param("other_attempt", "control_plane_anchor_mismatch", id="other-attempt"),
    ],
)
# Layer: integration
async def test_governed_operation_cache_requires_current_attempt_step_and_effect_anchor(
    tmp_path: Path, record_property, anchor: str, reason: str,
) -> None:
    case = make_case(tmp_path, [proposal()])
    await seed_open_cache(case, anchor=anchor)
    before_state = await control_plane_state(case)
    before_files = await immutable_physical(case)
    before_toolbox, before_hooks = case.toolbox.calls, len(case.probe.calls)

    turn, error = await _attempt(case, proposal())
    after_state = await control_plane_state(case)
    after_files = await immutable_physical(case)
    _record(record_property, anchor=anchor, turn_present=turn is not None,
        error=None if error is None else str(error), before_state=before_state, after_state=after_state,
        before_files=before_files, after_files=after_files)

    assert turn is None and error is not None
    assert f"E_OPERATION_ARTIFACT_INVALID:{reason}" in str(error)
    assert case.toolbox.calls == before_toolbox and len(case.probe.calls) == before_hooks
    _assert_rejected_call_finalized(before_state, after_state, before_files, after_files)


@pytest.mark.parametrize("raw", [pytest.param("{not-json", id="invalid-json"), pytest.param("[]", id="non-dict")])
# Layer: integration
async def test_governed_operation_cache_refuses_present_malformed_json_as_invalid(
    tmp_path: Path, record_property, raw: str,
) -> None:
    case = make_case(tmp_path, [proposal()])
    await seed_open_cache(case, anchor="absent", persist=False, execute_effect=False)
    await write_operation(case, raw)
    before_state = await control_plane_state(case)
    before_files = await immutable_physical(case)

    turn, error = await _attempt(case, proposal())
    after_state = await control_plane_state(case)
    after_files = await immutable_physical(case)
    _record(record_property, raw=raw, turn_present=turn is not None, error=None if error is None else str(error),
        before_state=before_state, after_state=after_state,
        before_files=before_files, after_files=after_files)

    assert turn is None and error is not None
    assert "E_OPERATION_ARTIFACT_INVALID:malformed" in str(error)
    assert case.toolbox.calls == 0 and case.probe.calls == []
    _assert_rejected_call_finalized(before_state, after_state, before_files, after_files)


# Layer: integration
async def test_governed_operation_cache_true_miss_executes_and_publishes_once(
    tmp_path: Path, record_property,
) -> None:
    case = make_case(tmp_path, [proposal()])
    await seed_open_cache(case, anchor="absent", persist=False, execute_effect=False)
    before_state = await control_plane_state(case)
    before_files = await immutable_physical(case)

    turn, error = await _attempt(case, proposal())
    after_state = await control_plane_state(case)
    after_files = await immutable_physical(case)
    _record(record_property, turn_present=turn is not None, error=None if error is None else str(error),
        before_state=before_state, after_state=after_state,
        before_files=before_files, after_files=after_files)

    assert error is None and turn is not None
    assert case.toolbox.calls == 1 and len(case.probe.calls) == 1
    assert before_files["operation"] is None and after_files["operation"] is not None
    assert before_files["receipt"] is None and after_files["receipt"] is not None
    assert after_state["run"]["lifecycle_state"] == RunState.COMPLETED.value
    assert after_state["step"] is not None and len(after_state["effects"]) == 1
    assert after_state["run"]["run_id"] == RUN_ID
