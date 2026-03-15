from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orket.streaming import CommitOrchestrator, InteractionManager, StreamBus
from orket.streaming.contracts import StreamEventType
from orket.workloads import run_builtin_workload
from tests.live.test_runtime_stability_closeout_live import _live_enabled, _live_model

pytestmark = pytest.mark.end_to_end


async def _drain_until_commit(queue: asyncio.Queue):
    events = []
    while True:
        event = await queue.get()
        events.append(event)
        if event.event_type == StreamEventType.COMMIT_FINAL:
            return events


def _configure_real_stream_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "real")
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "ollama")
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", _live_model())
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_TIMEOUT_S", "30")
    monkeypatch.setenv("ORKET_MODEL_STREAM_TURN_TIMEOUT_S", "30")


@pytest.mark.asyncio
async def test_model_stream_v1_live_repeated_cancel_before_first_token_interrupts(tmp_path: Path, monkeypatch) -> None:
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live streaming proof.")

    _configure_real_stream_env(monkeypatch)

    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"seed": 246}, {})
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    task = asyncio.create_task(
        run_builtin_workload(
            workload_id="model_stream_v1",
            input_config={
                "seed": 246,
                "prompt": "Count upward slowly from one and keep going.",
                "max_tokens": 128,
            },
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
            await manager.cancel(turn_id)
            break

    hints = await task
    if int(hints.get("request_cancel_turn", 0) or 0) > 0:
        await manager.cancel(turn_id)
    await manager.finalize(session_id, turn_id)
    seen.extend(await _drain_until_commit(queue))

    terminal_events = [
        event for event in seen if event.event_type in {StreamEventType.TURN_FINAL, StreamEventType.TURN_INTERRUPTED}
    ]
    commit_final = next(event for event in seen if event.event_type == StreamEventType.COMMIT_FINAL)

    print(
        "[live][stream][cancel-mid-gen] "
        f"session_id={session_id} turn_id={turn_id} "
        f"terminal={terminal_events[0].event_type.value} commit={commit_final.payload.get('commit_outcome')}"
    )
    assert len(terminal_events) == 1
    assert terminal_events[0].event_type == StreamEventType.TURN_INTERRUPTED
    assert terminal_events[0].payload["reason"] == "canceled"
    assert all(event.event_type != StreamEventType.TURN_FINAL for event in seen)
    assert commit_final.payload["commit_outcome"] == "ok"


@pytest.mark.asyncio
async def test_model_stream_v1_live_cancel_after_final_is_noop(tmp_path: Path, monkeypatch) -> None:
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live streaming proof.")

    _configure_real_stream_env(monkeypatch)

    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"seed": 247}, {})
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    await run_builtin_workload(
        workload_id="model_stream_v1",
        input_config={
            "seed": 247,
            "prompt": "Reply with the word OK exactly once.",
            "max_tokens": 8,
        },
        turn_params={},
        interaction_context=context,
    )
    await manager.finalize(session_id, turn_id)

    seen = []
    while True:
        event = await queue.get()
        seen.append(event)
        if event.event_type == StreamEventType.TURN_FINAL:
            break

    await manager.cancel(turn_id)
    await manager.cancel(turn_id)
    seen.extend(await _drain_until_commit(queue))

    terminal_events = [
        event for event in seen if event.event_type in {StreamEventType.TURN_FINAL, StreamEventType.TURN_INTERRUPTED}
    ]
    commit_final = next(event for event in seen if event.event_type == StreamEventType.COMMIT_FINAL)

    print(
        "[live][stream][cancel-after-final] "
        f"session_id={session_id} turn_id={turn_id} "
        f"terminal={terminal_events[0].event_type.value} commit={commit_final.payload.get('commit_outcome')}"
    )
    assert len(terminal_events) == 1
    assert terminal_events[0].event_type == StreamEventType.TURN_FINAL
    assert all(event.event_type != StreamEventType.TURN_INTERRUPTED for event in seen)
    assert commit_final.payload["commit_outcome"] == "ok"
