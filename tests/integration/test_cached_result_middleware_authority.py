"""Composed controls for cached after-tool middleware authority."""
from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from orket.application.middleware import MiddlewareOutcome
from orket.application.workflows.turn_artifact_writer import validate_operation_record
from orket.core.domain import (
    AttemptState,
    ClosureBasisClassification,
    ResultClass,
    RunState,
    SideEffectBoundaryClass,
)
from orket.core.domain.execution import ExecutionTurn, ToolCall, ToolCallErrorClass
from tests.helpers.cached_result_middleware import (
    compose_legacy_cached_result_leaf,
    observe_cached_result_load_leaf,
)
from tests.helpers.governed_operation_binding import seed_open_cache
from tests.helpers.operation_binding import (
    ARGS,
    ATTEMPT_ID,
    RUN_ID,
    captured_destination,
    context,
    control_plane_state,
    file_bytes,
    immutable_physical,
    make_case,
    operation_id,
    operation_record,
    proposal,
    seed_terminal,
    write_legacy_result,
    write_operation,
)
from tests.helpers.turn_artifacts import execute_executor_dispatch_fixture
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.usefixtures("deterministic_turn_clock"),
]


class _UnchangedHook:
    def __init__(self) -> None:
        self.calls = 0

    def after_tool(self, _tool_name, _args, result, **_kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return MiddlewareOutcome(replacement=deepcopy(result))


class _ReplacementHook:
    def __init__(self) -> None:
        self.calls = 0

    def after_tool(self, _tool_name, _args, result, **_kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return MiddlewareOutcome(replacement={**deepcopy(result), "middleware": {"changed": True}})


class _NestedResultMutationHook:
    def __init__(self) -> None:
        self.calls = 0

    def after_tool(self, _tool_name, _args, result, **_kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        result["touched_paths"][0] = "agent_output/middleware-changed.txt"
        return MiddlewareOutcome(replacement=result)


class _NestedArgsMutationHook:
    def __init__(self) -> None:
        self.calls = 0

    def after_tool(self, _tool_name, args, result, **_kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        args["options"]["mode"] = 1
        return MiddlewareOutcome(replacement=result)


async def _dispatch(
    case: Any,
    *,
    proposed: dict[str, Any] | None = None,
    resume: bool = False,
    protocol_enabled: bool = True,
) -> tuple[ExecutionTurn, object]:
    selected = proposal() if proposed is None else proposed
    turn = ExecutionTurn(
        timestamp=None,
        role=str(case.role.name),
        issue_id=str(case.issue.id),
        content="",
        tool_calls=[ToolCall(tool=selected["tool"], args=deepcopy(selected["args"]))],
    )
    operation = execute_executor_dispatch_fixture(
        case.executor,
        turn=turn,
        toolbox=case.toolbox,
        context={
            **context(resume=resume),
            "protocol_governed_enabled": protocol_enabled,
        },
        issue=case.issue,
    )
    outcome = (await asyncio.gather(operation, return_exceptions=True))[0]
    return turn, outcome


async def _legacy_path(case: Any, args: dict[str, Any]) -> Path:
    destination = await captured_destination(case)
    return await asyncio.to_thread(
        case.executor.artifact_writer.tool_result_path,
        destination=destination,
        tool_name="write_file",
        tool_args=args,
    )


def _attempt(state: dict[str, Any]) -> dict[str, Any]:
    return next(row for row in state["attempts"] if row["attempt_id"] == ATTEMPT_ID)


def _assert_open_boundary(state: dict[str, Any]) -> None:
    assert state["run"]["lifecycle_state"] == RunState.EXECUTING.value
    assert _attempt(state)["attempt_state"] == AttemptState.EXECUTING.value
    assert state["truth"] is None


def _assert_failed_after_effect_boundary(state: dict[str, Any]) -> None:
    attempt = _attempt(state)
    truth = state["truth"]
    assert state["run"]["lifecycle_state"] == RunState.FAILED_TERMINAL.value
    assert attempt["attempt_state"] == AttemptState.FAILED.value
    assert attempt["side_effect_boundary_class"] == SideEffectBoundaryClass.POST_EFFECT_OBSERVED.value
    assert truth["result_class"] == ResultClass.FAILED.value
    assert truth["closure_basis"] == ClosureBasisClassification.NORMAL_EXECUTION.value
    assert truth["authoritative_result_ref"] == f"turn-tool-violations:{RUN_ID}"


def _assert_completed_with_retained_effect(state: dict[str, Any]) -> None:
    attempt = _attempt(state)
    truth = state["truth"]
    assert state["run"]["lifecycle_state"] == RunState.COMPLETED.value
    assert attempt["attempt_state"] == AttemptState.COMPLETED.value
    assert attempt["side_effect_boundary_class"] is None
    assert state["effects"] and all(row["attempt_id"] == ATTEMPT_ID for row in state["effects"])
    assert truth["result_class"] == ResultClass.SUCCESS.value
    assert truth["closure_basis"] == ClosureBasisClassification.NORMAL_EXECUTION.value
    assert truth["authoritative_result_ref"] == f"turn-tool-result:{operation_id()}"


@pytest.mark.parametrize(
    ("hook_type", "stored_args", "reason"),
    [
        pytest.param(_ReplacementHook, ARGS, "result_changed", id="replacement"),
        pytest.param(_NestedResultMutationHook, ARGS, "result_changed", id="nested-result"),
        pytest.param(
            _NestedArgsMutationHook,
            {**ARGS, "options": {"mode": True}},
            "args_changed",
            id="nested-args-bool-int",
        ),
    ],
)
# Layer: integration
async def test_strict_cached_result_refuses_middleware_change_before_publication(
    tmp_path: Path,
    hook_type: type,
    stored_args: dict[str, Any],
    reason: str,
) -> None:
    case = make_case(tmp_path, [proposal(args=stored_args)])
    await seed_open_cache(case, anchor="coherent", stored_args=stored_args)
    hook = hook_type()
    case.executor.middleware.register(hook)
    before_state = await control_plane_state(case)
    before = {name: await file_bytes(case, name) for name in ("operation", "receipt", "effect")}
    _assert_open_boundary(before_state)

    turn, outcome = await _dispatch(case, proposed=proposal(args=stored_args))
    after_state = await control_plane_state(case)
    after = {name: await file_bytes(case, name) for name in ("operation", "receipt", "effect")}
    call = turn.tool_calls[0]

    assert isinstance(outcome, BaseException)
    assert call.result is None
    assert call.error_class is ToolCallErrorClass.EXECUTION_FAILED
    assert f"E_CACHED_RESULT_MIDDLEWARE_AUTHORITY:{reason}" in str(call.error)
    assert hook.calls == 1 and case.toolbox.calls == 1
    assert after == before
    assert after_state["step"] == before_state["step"]
    assert after_state["effects"] == before_state["effects"]
    _assert_failed_after_effect_boundary(after_state)


# Layer: integration
async def test_healthy_strict_cache_keeps_reformatted_operation_bytes(
    tmp_path: Path,
) -> None:
    case = make_case(tmp_path, [proposal()])
    seeded = await seed_open_cache(case, anchor="coherent")
    stored = await operation_record(case)
    assert stored is not None
    compact = json.dumps(stored, sort_keys=True, separators=(",", ":"))
    await write_operation(case, compact)
    hook = _UnchangedHook()
    case.executor.middleware.register(hook)
    before_state = await control_plane_state(case)
    operation_before = await file_bytes(case, "operation")
    receipt_before = await file_bytes(case, "receipt")
    _assert_open_boundary(before_state)

    turn, outcome = await _dispatch(case)
    after_state = await control_plane_state(case)
    operation_after = await file_bytes(case, "operation")
    receipt_after = await file_bytes(case, "receipt")
    retained = await operation_record(case)

    assert not isinstance(outcome, BaseException)
    assert hook.calls == 1 and case.toolbox.calls == 1
    assert turn.tool_calls[0].result == seeded.result
    assert operation_before is not None and operation_after == operation_before
    assert retained == stored
    assert retained["result_digest"] == stored["result_digest"]
    assert receipt_before is None and receipt_after is not None
    assert after_state["step"] == before_state["step"]
    assert after_state["effects"] == before_state["effects"]
    _assert_completed_with_retained_effect(after_state)


@pytest.mark.parametrize("protocol_enabled", [True, False], ids=["protocol", "nonprotocol-governed"])
# Layer: integration
async def test_legacy_cache_materializes_missing_operation_without_rewriting_legacy(
    tmp_path: Path,
    protocol_enabled: bool,
) -> None:
    case = make_case(tmp_path, [proposal()])
    seeded = await seed_open_cache(case, anchor="coherent", persist=False)
    await write_legacy_result(case, args=ARGS, result=seeded.result)
    legacy_path = await _legacy_path(case, ARGS)
    compact = json.dumps(seeded.result, sort_keys=True, separators=(",", ":"))
    await asyncio.to_thread(legacy_path.write_text, compact, encoding="utf-8")
    legacy_before = await asyncio.to_thread(legacy_path.read_bytes)
    assert await file_bytes(case, "operation") is None
    assert await file_bytes(case, "receipt") is None
    hook = _UnchangedHook()
    case.executor.middleware.register(hook)
    before_state = await control_plane_state(case)

    # Leaf composition proves cache/middleware/publication ownership. Public resume
    # remains subject to checkpoint admission and retained-effect reconciliation.
    turn, outcome = await compose_legacy_cached_result_leaf(
        case,
        protocol_enabled=protocol_enabled,
    )
    after_state = await control_plane_state(case)
    legacy_after = await asyncio.to_thread(legacy_path.read_bytes)
    retained = await operation_record(case)

    assert not isinstance(outcome, BaseException)
    assert hook.calls == 1 and case.toolbox.calls == 1
    assert turn.tool_calls[0].result == seeded.result
    assert legacy_after == legacy_before
    assert retained is not None
    assert validate_operation_record(
        retained,
        operation_id=operation_id(),
        tool_name="write_file",
        tool_args=ARGS,
    ) == seeded.result
    if protocol_enabled:
        assert await file_bytes(case, "receipt") is not None
    else:
        assert await file_bytes(case, "receipt") is None
    assert after_state["step"] == before_state["step"]
    assert after_state["effects"] == before_state["effects"]
    _assert_completed_with_retained_effect(after_state)


# Layer: integration
async def test_nonprotocol_governed_present_invalid_operation_does_not_fall_back_to_legacy(
    tmp_path: Path,
) -> None:
    case = make_case(tmp_path, [proposal()])
    seeded = await seed_open_cache(case, anchor="coherent")
    await write_legacy_result(case, args=ARGS, result=seeded.result)
    legacy_path = await _legacy_path(case, ARGS)
    legacy_before = await asyncio.to_thread(legacy_path.read_bytes)
    await write_operation(case, "{not-json")
    before_state = await control_plane_state(case)
    before = {name: await file_bytes(case, name) for name in ("operation", "receipt", "effect")}
    _assert_open_boundary(before_state)

    turn, outcome = await observe_cached_result_load_leaf(case, protocol_enabled=False)
    after_state = await control_plane_state(case)
    after = {name: await file_bytes(case, name) for name in ("operation", "receipt", "effect")}

    assert isinstance(outcome, BaseException)
    assert turn.tool_calls[0].result is None
    assert "E_OPERATION_ARTIFACT_INVALID:malformed" in str(outcome)
    assert case.toolbox.calls == 1 and case.probe.calls == []
    assert after == before
    assert await asyncio.to_thread(legacy_path.read_bytes) == legacy_before
    assert after_state == before_state
    _assert_open_boundary(after_state)


# Layer: integration
async def test_embedded_replay_refuses_changed_middleware_result_without_authority_mutation(
    tmp_path: Path,
) -> None:
    case = make_case(tmp_path, [proposal(), proposal()])
    await seed_terminal(case, success=True)
    hook = _ReplacementHook()
    case.executor.middleware.register(hook)
    before_state = await control_plane_state(case)
    before_files = await immutable_physical(case)

    result = await case.executor.execute_turn(
        case.issue,
        case.role,
        case.model,
        case.toolbox,
        context(replay=True),
        system_prompt="SYSTEM",
    )
    after_state = await control_plane_state(case)
    after_files = await immutable_physical(case)

    assert result.success is False and result.turn is None
    assert result.error is not None
    assert "E_CACHED_RESULT_MIDDLEWARE_AUTHORITY:result_changed" in result.error
    assert hook.calls == 1 and len(case.probe.calls) == 2
    assert case.model.calls == 2 and case.toolbox.calls == 1
    assert after_state == before_state
    assert after_files == before_files


# Layer: integration
async def test_live_after_tool_replacement_remains_authoritative(
    tmp_path: Path,
) -> None:
    case = make_case(tmp_path, [proposal()])
    hook = _ReplacementHook()
    case.executor.middleware.register(hook)

    turn, outcome = await _dispatch(case)
    retained = await operation_record(case)
    call = turn.tool_calls[0]

    assert not isinstance(outcome, BaseException)
    assert hook.calls == 1 and case.toolbox.calls == 1
    assert call.error is None
    assert call.result is not None and call.result["middleware"] == {"changed": True}
    assert retained is not None and retained["result"] == call.result
    assert retained["result_digest"] == case.executor.artifact_writer.hash_payload(call.result)
    assert await file_bytes(case, "receipt") is not None


# Layer: integration
async def test_nonprotocol_governed_strict_cache_preserves_reformatted_operation(
    tmp_path: Path,
) -> None:
    case = make_case(tmp_path, [proposal()])
    seeded = await seed_open_cache(case, anchor="coherent")
    stored = await operation_record(case)
    assert stored is not None
    await write_operation(case, json.dumps(stored, sort_keys=True, separators=(",", ":")))
    hook = _UnchangedHook()
    case.executor.middleware.register(hook)
    before_state = await control_plane_state(case)
    operation_before = await file_bytes(case, "operation")
    _assert_open_boundary(before_state)

    turn, outcome = await _dispatch(case, protocol_enabled=False)
    after_state = await control_plane_state(case)

    assert not isinstance(outcome, BaseException)
    assert hook.calls == 1 and case.toolbox.calls == 1
    assert turn.tool_calls[0].result == seeded.result
    assert await file_bytes(case, "operation") == operation_before
    assert await file_bytes(case, "receipt") is None
    assert after_state["step"] == before_state["step"]
    assert after_state["effects"] == before_state["effects"]
    _assert_completed_with_retained_effect(after_state)
