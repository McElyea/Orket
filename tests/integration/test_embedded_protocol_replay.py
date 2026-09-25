"""Composed contract controls for the embedded TurnExecutor replay flag."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.operation_binding import (
    ARGS,
    ControlledModel,
    PhysicalToolbox,
    artifact_paths,
    before_after,
    context,
    expected_reentry,
    local_prefix,
    make_case,
    mutate_record,
    observe_reentry_and_forbid_owner,
    proposal,
    seed_terminal,
    write_operation,
)
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]


def _property(record_property, **payload):  # type: ignore[no-untyped-def]
    record_property("embedded_replay_observation", json.dumps(payload, sort_keys=True))


# Layer: integration
async def test_embedded_replay_consults_completed_success_and_reuses_recorded_operation(
    tmp_path: Path, monkeypatch, record_property,
) -> None:
    case = make_case(tmp_path, [proposal(), proposal()])
    seed = await seed_terminal(case, success=True)
    reentries, owner_calls = observe_reentry_and_forbid_owner(case, monkeypatch)
    local_before = await local_prefix(case)

    async def replay():
        return await case.executor.execute_turn(
            case.issue, case.role, case.model, case.toolbox, context(replay=True), system_prompt="SYSTEM"
        )

    result, before_state, after_state, before_files, after_files = await before_after(case, replay)
    local_after = await local_prefix(case)
    _property(record_property, result_success=result.success, model_calls=case.model.calls,
        toolbox_calls=case.toolbox.calls, physical_before=before_files, physical_after=after_files,
        local_before=local_before, local_after=local_after)

    assert result.success is True and result.turn is not None
    assert result.turn.content == ""
    assert result.turn.tokens_used == 2
    assert result.turn.tool_calls[0].result == seed.operation["result"]
    assert case.model.calls == 2 and case.toolbox.calls == 1
    assert reentries == [expected_reentry()] and owner_calls == []
    assert after_state == before_state == seed.state
    assert after_files == before_files


# Layer: integration
async def test_embedded_replay_refuses_failed_terminal_before_model_or_toolbox(
    tmp_path: Path, monkeypatch, record_property,
) -> None:
    case = make_case(tmp_path, [proposal()], fail=True)
    seed = await seed_terminal(case, success=False)
    replay_model = ControlledModel([proposal()])
    replay_toolbox = PhysicalToolbox(case.workspace)
    reentries, owner_calls = observe_reentry_and_forbid_owner(case, monkeypatch)
    local_before = await local_prefix(case)

    async def replay():
        return await case.executor.execute_turn(
            case.issue, case.role, replay_model, replay_toolbox, context(replay=True), system_prompt="SYSTEM"
        )

    result, before_state, after_state, before_files, after_files = await before_after(case, replay)
    local_after = await local_prefix(case)
    _property(record_property, result_success=result.success, result_error=result.error,
        model_calls=replay_model.calls, toolbox_calls=replay_toolbox.calls,
        physical_before=before_files, physical_after=after_files,
        local_before=local_before, local_after=local_after)

    assert result.success is False and result.should_retry is False
    assert result.error is not None and "already closed with failed via normal_execution" in result.error
    assert replay_model.calls == 0 and replay_toolbox.calls == 0
    assert reentries == [expected_reentry()] and owner_calls == []
    assert after_state == before_state == seed.state
    assert after_files == before_files


@pytest.mark.parametrize(
    ("proposed", "error_fragment", "reason"),
    [
        pytest.param(proposal(args={**ARGS, "content": "effect-b"}),
            "arguments do not match", "args_mismatch", id="args"),
        pytest.param(proposal("create_directory", {"path": "agent_output/changed-operation"}),
            "does not match", "tool_mismatch", id="tool"),
    ],
)
# Layer: integration
async def test_embedded_replay_refuses_same_slot_operation_with_changed_call(
    tmp_path: Path,
    monkeypatch,
    record_property,
    proposed: dict[str, Any],
    error_fragment: str,
    reason: str,
) -> None:
    case = make_case(tmp_path, [proposal(), proposed])
    if proposed["tool"] not in case.role.tools:
        case.role = case.role.model_copy(update={"tools": [*case.role.tools, str(proposed["tool"])]})
    seed = await seed_terminal(case, success=True)
    reentries, owner_calls = observe_reentry_and_forbid_owner(case, monkeypatch)
    local_before = await local_prefix(case)

    async def replay():
        return await case.executor.execute_turn(
            case.issue, case.role, case.model, case.toolbox, context(replay=True), system_prompt="SYSTEM"
        )

    result, before_state, after_state, before_files, after_files = await before_after(case, replay)
    local_after = await local_prefix(case)
    _property(record_property, proposed_call=proposed,
        stored_call={"tool": seed.operation["tool"], "args": seed.operation["args"]},
        result_success=result.success, result_error=result.error, model_calls=case.model.calls,
        toolbox_calls=case.toolbox.calls, physical_before=before_files, physical_after=after_files,
        local_before=local_before, local_after=local_after)

    assert result.success is False
    assert result.error is not None and error_fragment in result.error
    assert f"E_OPERATION_ARTIFACT_INVALID:{reason}" in result.error
    assert case.model.calls == 2 and case.toolbox.calls == 1
    assert reentries == [expected_reentry()] and owner_calls == []
    assert after_state == before_state == seed.state
    assert after_files == before_files


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        pytest.param("operation_id", "E_OPERATION_ARTIFACT_INVALID:operation_id_mismatch", id="operation-id"),
        pytest.param("result", "E_OPERATION_ARTIFACT_INVALID:result_digest_mismatch", id="result-only"),
        pytest.param("digest", "E_OPERATION_ARTIFACT_INVALID:result_digest_mismatch", id="digest-only"),
        pytest.param("missing_digest", "E_OPERATION_ARTIFACT_INVALID:malformed", id="missing-digest"),
        pytest.param("malformed_digest", "E_OPERATION_ARTIFACT_INVALID:malformed", id="malformed-digest"),
        pytest.param("missing", "E_REPLAY_OPERATION_MISSING", id="missing-record"),
        pytest.param("invalid_json", "E_OPERATION_ARTIFACT_INVALID:malformed", id="invalid-json"),
        pytest.param("non_dict", "E_OPERATION_ARTIFACT_INVALID:malformed", id="non-dict"),
    ],
)
# Layer: integration
async def test_embedded_replay_refuses_missing_or_present_invalid_operation_record(
    tmp_path: Path, monkeypatch, record_property, mutation: str, expected_error: str,
) -> None:
    case = make_case(tmp_path, [proposal(), proposal()])
    seed = await seed_terminal(case, success=True)
    if mutation == "missing":
        await asyncio.to_thread((await artifact_paths(case))["operation"].unlink)
    elif mutation == "invalid_json":
        await write_operation(case, "{not-json")
    elif mutation == "non_dict":
        await write_operation(case, "[]")
    else:
        await write_operation(case, mutate_record(seed.operation, mutation))
    reentries, owner_calls = observe_reentry_and_forbid_owner(case, monkeypatch)
    local_before = await local_prefix(case)

    async def replay():
        return await case.executor.execute_turn(
            case.issue, case.role, case.model, case.toolbox, context(replay=True), system_prompt="SYSTEM"
        )

    result, before_state, after_state, before_files, after_files = await before_after(case, replay)
    local_after = await local_prefix(case)
    _property(record_property, mutation=mutation, expected_error=expected_error,
        result_success=result.success, result_error=result.error, physical_before=before_files,
        physical_after=after_files, local_before=local_before, local_after=local_after)

    assert result.success is False
    assert result.error is not None and expected_error in result.error
    assert case.model.calls == 2 and case.toolbox.calls == 1 and len(case.probe.calls) == 1
    assert reentries == [expected_reentry()] and owner_calls == []
    assert after_state == before_state and after_files == before_files


# Layer: integration
async def test_embedded_replay_distinguishes_bool_from_int_arguments(
    tmp_path: Path, monkeypatch, record_property,
) -> None:
    stored_args = {**ARGS, "mode": True}
    proposed_args = {**ARGS, "mode": 1}
    case = make_case(tmp_path, [proposal(args=stored_args), proposal(args=proposed_args)])
    await seed_terminal(case, success=True)
    reentries, owner_calls = observe_reentry_and_forbid_owner(case, monkeypatch)

    async def replay():
        return await case.executor.execute_turn(
            case.issue, case.role, case.model, case.toolbox, context(replay=True), system_prompt="SYSTEM"
        )

    result, before_state, after_state, before_files, after_files = await before_after(case, replay)
    _property(record_property, stored_args=stored_args, proposed_args=proposed_args,
        result_success=result.success, result_error=result.error,
        physical_before=before_files, physical_after=after_files)

    assert result.success is False
    assert result.error is not None and "E_OPERATION_ARTIFACT_INVALID:args_mismatch" in result.error
    assert case.model.calls == 2 and case.toolbox.calls == 1 and len(case.probe.calls) == 1
    assert reentries == [expected_reentry()] and owner_calls == []
    assert after_state == before_state and after_files == before_files
