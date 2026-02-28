from __future__ import annotations

import asyncio

import pytest

from orket.streaming import CommitOrchestrator, InteractionManager, StreamBus, StreamBusConfig
from orket.streaming.contracts import StreamEventType
from orket.workloads import run_builtin_workload


async def _drain_until_commit(queue: asyncio.Queue):
    events = []
    while True:
        event = await queue.get()
        events.append(event)
        if event.event_type == StreamEventType.COMMIT_FINAL:
            return events


@pytest.mark.asyncio
async def test_stream_test_spam_deltas_emits_drop_ranges_and_commit_ok(tmp_path):
    manager = InteractionManager(
        bus=StreamBus(
            StreamBusConfig(
                best_effort_max_events_per_turn=8,
                bounded_max_events_per_turn=32,
                max_bytes_per_turn_queue=10_000,
            )
        ),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"seed": 7}, {})
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    await run_builtin_workload(
        workload_id="stream_test_v1",
        input_config={"mode": "spam_deltas", "seed": 7, "delta_count": 80, "chunk_size": 2},
        turn_params={},
        interaction_context=context,
    )
    await manager.finalize(session_id, turn_id)
    events = await _drain_until_commit(queue)

    turn_final = next(event for event in events if event.event_type == StreamEventType.TURN_FINAL)
    assert "dropped_seq_ranges" in turn_final.payload
    commit_final = next(event for event in events if event.event_type == StreamEventType.COMMIT_FINAL)
    assert commit_final.payload["commit_outcome"] == "ok"


@pytest.mark.asyncio
async def test_stream_test_finalize_then_wait_cancel_after_final_is_noop(tmp_path):
    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"seed": 9}, {})
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    hints = await run_builtin_workload(
        workload_id="stream_test_v1",
        input_config={"mode": "finalize_then_wait", "seed": 9, "wait_ms": 40},
        turn_params={},
        interaction_context=context,
    )
    await manager.finalize(session_id, turn_id)

    buffered = []
    while True:
        event = await queue.get()
        buffered.append(event)
        if event.event_type == StreamEventType.TURN_FINAL:
            break

    await manager.cancel(turn_id)
    if hints.get("post_finalize_wait_ms", 0) > 0:
        await asyncio.sleep(int(hints["post_finalize_wait_ms"]) / 1000.0)
    buffered.extend(await _drain_until_commit(queue))

    terminal_events = [event for event in buffered if event.event_type in {StreamEventType.TURN_FINAL, StreamEventType.TURN_INTERRUPTED}]
    assert len(terminal_events) == 1
    assert terminal_events[0].event_type == StreamEventType.TURN_FINAL
    assert all(event.event_type != StreamEventType.TURN_INTERRUPTED for event in buffered)


@pytest.mark.asyncio
async def test_model_stream_v1_stub_path_commits_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "stub")
    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"seed": 5}, {})
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    await run_builtin_workload(
        workload_id="model_stream_v1",
        input_config={"seed": 5, "mode": "basic"},
        turn_params={},
        interaction_context=context,
    )
    await manager.finalize(session_id, turn_id)
    events = await _drain_until_commit(queue)

    event_types = [event.event_type for event in events]
    assert StreamEventType.MODEL_SELECTED in event_types
    assert StreamEventType.MODEL_LOADING in event_types
    assert StreamEventType.MODEL_READY in event_types
    assert StreamEventType.TOKEN_DELTA in event_types
    commit_final = next(event for event in events if event.event_type == StreamEventType.COMMIT_FINAL)
    assert commit_final.payload["commit_outcome"] == "ok"


@pytest.mark.asyncio
async def test_model_stream_v1_stub_cancel_before_first_token_interrupts(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "stub")
    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"seed": 5}, {})
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    task = asyncio.create_task(
        run_builtin_workload(
            workload_id="model_stream_v1",
            input_config={"seed": 5, "mode": "basic", "first_token_delay_ms": 100},
            turn_params={},
            interaction_context=context,
        )
    )

    seen = []
    while True:
        event = await queue.get()
        seen.append(event)
        if event.event_type == StreamEventType.MODEL_LOADING:
            await manager.cancel(turn_id)
            break

    await task
    await manager.finalize(session_id, turn_id)
    seen.extend(await _drain_until_commit(queue))

    terminal_events = [event for event in seen if event.event_type in {StreamEventType.TURN_FINAL, StreamEventType.TURN_INTERRUPTED}]
    assert len(terminal_events) == 1
    assert terminal_events[0].event_type == StreamEventType.TURN_INTERRUPTED
    assert all(event.event_type != StreamEventType.TURN_FINAL for event in seen)
