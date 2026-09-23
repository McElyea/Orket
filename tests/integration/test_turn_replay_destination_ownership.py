"""Layer: integration. Reentry retains its admitted destination and service."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orket.core.domain.execution import ExecutionTurn, ToolCall
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.turn_artifacts import write_checkpoint_fixture
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_turn_artifact_destination_ownership import (
    _RUN_A,
    _assert_no_drift_control_plane,
    _case,
    _json,
    _mutate,
    _turn_dir,
    _turn_task,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.usefixtures("deterministic_turn_clock"),
]


async def _records(case):
    run = await case.service.execution_repository.get_run_record(run_id=_RUN_A)
    assert run is not None and run.current_attempt_id is not None
    attempt = await case.service.execution_repository.get_attempt_record(
        attempt_id=run.current_attempt_id
    )
    checkpoint = await case.service.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{run.current_attempt_id}"
    )
    steps = await case.service.execution_repository.list_step_records(attempt_id=run.current_attempt_id)
    effects = await case.service.publication.repository.list_effect_journal_entries(run_id=_RUN_A)
    truth = await case.service.publication.repository.get_final_truth(run_id=_RUN_A)
    assert attempt is not None and checkpoint is not None
    return run, attempt, checkpoint, steps, effects, truth


async def _snapshot_bytes(case) -> tuple[Path, bytes]:
    paths = await asyncio.to_thread(
        lambda: sorted(_turn_dir(case).glob("control_plane_checkpoint_snapshot_*.json"))
    )
    assert len(paths) == 1
    return paths[0], await asyncio.to_thread(paths[0].read_bytes)


def _reset_owner(case) -> None:
    case.owner.entered.clear()
    case.owner.release.clear()
    case.owner.keys.clear()


async def _assert_a_effect(case) -> None:
    assert case.toolbox.contexts == [
        {"session_id": "session-a", "issue_id": "ISSUE-A", "role": "developer-a", "turn_index": 3}
    ]
    assert case.toolbox.effect_paths == ["effects/session-a_ISSUE-A_developer-a_3.txt"]
    assert await case.toolbox.files.read_file("agent_output/out.txt") == "ok"
    assert await case.toolbox.files.read_file(case.toolbox.effect_paths[0]) == "ok"


async def _assert_a_trace(case) -> None:
    trace = await _json(_turn_dir(case) / "memory_trace.json")
    assert (trace["run_id"], trace["issue_id"], trace["role_id"]) == (
        "session-a",
        "ISSUE-A",
        "ROLE-A",
    )


async def _assert_no_b_artifacts(case, tmp_path: Path) -> None:
    await _assert_no_drift_control_plane(case)
    assert not await asyncio.to_thread((tmp_path / "workspace-b" / "observability").exists)
    assert not await asyncio.to_thread((case.root / "observability" / "session-b").exists)


async def test_completed_replay_keeps_admitted_destination_service_and_record_time(
    tmp_path, monkeypatch, record_property, deterministic_turn_clock,
) -> None:
    case = _case(tmp_path, monkeypatch, deterministic_turn_clock, held_model=False)
    async with _turn_task(case) as task:
        await asyncio.wait_for(case.owner.entered.wait(), 5)
        case.owner.release.set()
        seeded = await asyncio.wait_for(asyncio.shield(task), 15)
    assert seeded.success and seeded.turn is not None
    before = await _records(case)
    snapshot_path, snapshot_before = await _snapshot_bytes(case)
    clock_count = len(case.clock.observations)

    _reset_owner(case)
    async with _turn_task(case) as task:
        await asyncio.wait_for(case.owner.entered.wait(), 5)
        assert case.owner.keys == [_RUN_A]
        await responsive_sqlite(
            tmp_path / "replay-responsive.sqlite3",
            lambda key, value: record_property(f"replay_{key}", value),
        )
        _mutate(case, tmp_path, "B")
        case.owner.release.set()
        replayed = await asyncio.wait_for(asyncio.shield(task), 15)

    after = await _records(case)
    assert replayed.success and replayed.turn is not None
    assert (replayed.turn.issue_id, replayed.turn.role) == ("ISSUE-A", "developer-a")
    assert replayed.turn.note == "control_plane_completed_replay" and replayed.turn.timestamp is None
    assert replayed.turn.raw["control_plane_replay"]["run_id"] == _RUN_A
    assert case.model.calls == 1 and len(case.toolbox.contexts) == 1
    assert len(case.clock.observations) == clock_count
    assert (after[0].creation_timestamp, after[1].start_timestamp, after[2].creation_timestamp) == (
        before[0].creation_timestamp, before[1].start_timestamp, before[2].creation_timestamp,
    )
    assert after[0].final_truth_record_id == before[0].final_truth_record_id
    assert len(after[3]) == len(after[4]) == 1 and after[5] is not None
    assert after[0].namespace_scope == after[3][0].namespace_scope == "issue:ISSUE-A"
    assert await asyncio.to_thread(snapshot_path.read_bytes) == snapshot_before
    await _assert_a_effect(case)
    await _assert_a_trace(case)
    await _assert_no_b_artifacts(case, tmp_path)


async def test_pre_effect_resume_keeps_admitted_destination_service_and_record_time(
    tmp_path, monkeypatch, record_property, deterministic_turn_clock,
) -> None:
    case = _case(tmp_path, monkeypatch, deterministic_turn_clock, held_model=False)
    pre_effect_turn = ExecutionTurn(
        timestamp=None,
        role="developer-a",
        issue_id="ISSUE-A",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "agent_output/out.txt", "content": "ok"})],
    )
    await write_checkpoint_fixture(
        executor=case.executor,
        turn=pre_effect_turn,
        context=case.context,
        prompt_hash="prompt-hash-seeded",
    )
    before = await _records(case)
    snapshot_path, snapshot_before = await _snapshot_bytes(case)
    case.context["resume_mode"] = True

    async with _turn_task(case) as task:
        await asyncio.wait_for(case.owner.entered.wait(), 5)
        assert case.owner.keys == [_RUN_A]
        await responsive_sqlite(
            tmp_path / "resume-responsive.sqlite3",
            lambda key, value: record_property(f"resume_{key}", value),
        )
        _mutate(case, tmp_path, "B")
        case.owner.release.set()
        resumed = await asyncio.wait_for(asyncio.shield(task), 15)

    after = await _records(case)
    assert resumed.success and resumed.turn is not None
    assert (resumed.turn.issue_id, resumed.turn.role) == ("ISSUE-A", "developer-a")
    assert resumed.turn.note == "control_plane_checkpoint_resume" and resumed.turn.timestamp is None
    assert resumed.turn.raw["control_plane_resume"]["run_id"] == _RUN_A
    assert case.model.calls == 0 and len(case.toolbox.contexts) == 1
    assert (after[0].creation_timestamp, after[1].start_timestamp, after[2].creation_timestamp) == (
        before[0].creation_timestamp, before[1].start_timestamp, before[2].creation_timestamp,
    )
    assert after[0].lifecycle_state.value == "completed"
    assert len(after[3]) == len(after[4]) == 1 and after[5] is not None
    assert after[0].namespace_scope == after[3][0].namespace_scope == "issue:ISSUE-A"
    assert await asyncio.to_thread(snapshot_path.read_bytes) == snapshot_before
    await _assert_a_effect(case)
    await _assert_a_trace(case)
    await _assert_no_b_artifacts(case, tmp_path)
