"""Integration controls for cached-result determinism refusal."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.application.services.turn_tool_control_plane_support import (
    governed_tool_call_digest,
    tool_call_ref,
)
from orket.application.workflows.turn_executor import ToolValidationError
from orket.core.contracts.protocol_error_codes import (
    E_DETERMINISM_VIOLATION_PREFIX,
    format_protocol_error,
)
from orket.core.contracts.tool_invocation_contracts import compute_tool_call_hash
from orket.core.domain import AttemptState, ClosureBasisClassification, ResultClass, RunState, SideEffectBoundaryClass
from orket.core.domain.execution import ExecutionTurn, ToolCall
from tests.helpers.operation_binding import (
    ARGS,
    ATTEMPT_ID,
    ISSUE,
    ROLE,
    RUN_ID,
    SESSION,
    TURN,
    captured_destination,
    context,
    control_plane_state,
    file_bytes,
    make_case,
    operation_id,
    operation_record,
    proposal,
)
from tests.helpers.turn_artifacts import execute_executor_dispatch_fixture
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]

PURE_BINDING = {
    "ring": "core",
    "capability_profile": "workspace",
    "determinism_class": "pure",
    "tool_contract_version": "1.0.0",
}
DIAGNOSTIC = format_protocol_error(E_DETERMINISM_VIOLATION_PREFIX, "write_file:declared_pure")


def _context(*, replay: bool = False) -> dict[str, Any]:
    value = dict(context(replay=replay))
    value["skill_tool_bindings"] = {"write_file": dict(PURE_BINDING)}
    return value


async def _attempt(case, *, replay: bool = False):  # type: ignore[no-untyped-def]
    turn = ExecutionTurn(
        timestamp=None,
        role=ROLE,
        issue_id=ISSUE,
        content="",
        tool_calls=[ToolCall(tool="write_file", args=dict(ARGS))],
    )
    try:
        await execute_executor_dispatch_fixture(
            case.executor,
            turn=turn,
            toolbox=case.toolbox,
            context=_context(replay=replay),
            issue=case.issue,
        )
    except (ToolValidationError, TurnToolControlPlaneError, RuntimeError, ValueError) as error:
        return turn, error
    return turn, None


async def _seed_open_cache(case):  # type: ignore[no-untyped-def]
    run, attempt = await case.service.begin_execution(
        session_id=SESSION,
        issue_id=ISSUE,
        role_name=ROLE,
        turn_index=TURN,
        proposal_hash="seed-proposal",
    )
    result = await case.toolbox.execute("write_file", ARGS, _context())
    selected = await captured_destination(case)
    await asyncio.to_thread(
        case.executor.artifact_writer.persist_operation_result,
        destination=selected,
        operation_id=operation_id(),
        tool_name="write_file",
        tool_args=ARGS,
        result=result,
    )
    await case.service.publish_step_result(
        run_id=run.run_id,
        attempt_id=attempt.attempt_id,
        step_id=operation_id(),
        tool_name="write_file",
        tool_args=ARGS,
        result=result,
        binding=dict(PURE_BINDING),
        operation_id=operation_id(),
        replayed=False,
    )
    return result


async def _artifact_bytes(case) -> dict[str, bytes | None]:  # type: ignore[no-untyped-def]
    return {name: await file_bytes(case, name) for name in ("operation", "receipt", "effect")}


def _expected_input_ref() -> str:
    return tool_call_ref(tool_call_digest=governed_tool_call_digest(
        tool_name="write_file",
        tool_args=ARGS,
        binding=PURE_BINDING,
        operation_id=operation_id(),
    ))


# Layer: integration
async def test_governed_cached_determinism_violation_refuses_without_republication(
    tmp_path: Path,
) -> None:
    case = make_case(tmp_path, [proposal()])
    cached = await _seed_open_cache(case)
    before_state = await control_plane_state(case)
    before_artifacts = await _artifact_bytes(case)
    assert before_state["step"]["input_ref"] == _expected_input_ref()
    assert before_artifacts["receipt"] is None

    turn, error = await _attempt(case)
    after_state = await control_plane_state(case)
    after_artifacts = await _artifact_bytes(case)
    attempt = next(row for row in after_state["attempts"] if row["attempt_id"] == ATTEMPT_ID)

    assert error is not None and DIAGNOSTIC in str(error)
    assert turn.tool_calls[0].result is None
    assert case.toolbox.calls == 1 and len(case.probe.calls) == 1
    assert (await operation_record(case))["result"] == cached
    assert after_artifacts == before_artifacts
    assert after_state["step"] == before_state["step"]
    assert after_state["effects"] == before_state["effects"]
    assert after_state["step"]["input_ref"] == _expected_input_ref()
    assert after_state["run"]["lifecycle_state"] == RunState.FAILED_TERMINAL.value
    assert attempt["attempt_state"] == AttemptState.FAILED.value
    assert attempt["side_effect_boundary_class"] == SideEffectBoundaryClass.POST_EFFECT_OBSERVED.value
    assert attempt["failure_class"] == "tool_execution_failed"
    assert after_state["truth"]["result_class"] == ResultClass.FAILED.value
    assert after_state["truth"]["closure_basis"] == ClosureBasisClassification.NORMAL_EXECUTION.value
    assert after_state["truth"]["authoritative_result_ref"] == f"turn-tool-violations:{RUN_ID}"


# Layer: integration
async def test_embedded_cached_determinism_violation_preserves_existing_terminal_truth(
    tmp_path: Path,
) -> None:
    case = make_case(tmp_path, [proposal()])
    live_turn, live_error = await _attempt(case)
    assert live_error is not None and DIAGNOSTIC in str(live_error)
    assert live_turn.tool_calls[0].result["error"] == DIAGNOSTIC
    assert case.toolbox.calls == 1 and len(case.probe.calls) == 1

    before_state = await control_plane_state(case)
    before_artifacts = await _artifact_bytes(case)
    stored = await operation_record(case)
    assert stored is not None and stored["result"] == live_turn.tool_calls[0].result
    receipt = json.loads((before_artifacts["receipt"] or b"").decode("utf-8").splitlines()[-1])
    assert receipt["tool_call_hash"] == compute_tool_call_hash(
        tool_name="write_file",
        tool_args=ARGS,
        tool_contract_version=PURE_BINDING["tool_contract_version"],
        capability_profile=PURE_BINDING["capability_profile"],
    )

    replay_turn, replay_error = await _attempt(case, replay=True)
    after_state = await control_plane_state(case)
    after_artifacts = await _artifact_bytes(case)

    assert replay_error is not None and DIAGNOSTIC in str(replay_error)
    assert replay_turn.tool_calls[0].result is None
    assert case.toolbox.calls == 1 and len(case.probe.calls) == 2
    assert after_artifacts == before_artifacts
    assert after_state == before_state
