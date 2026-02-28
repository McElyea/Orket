from __future__ import annotations

import pytest

from orket.streaming import CommitOrchestrator, InteractionManager, StreamBus
from orket.streaming.contracts import CommitIntent, StreamEventType


@pytest.mark.asyncio
async def test_manager_begin_turn_emits_turn_accepted_and_linear_policy(tmp_path):
    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({"npc": "guard"})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"text": "hi"}, {"persona": "guard"})
    event = await queue.get()
    assert event.event_type == StreamEventType.TURN_ACCEPTED
    assert event.turn_id == turn_id
    with pytest.raises(ValueError):
        await manager.begin_turn(session_id, {"text": "again"}, {})


@pytest.mark.asyncio
async def test_manager_cancel_then_finalize_emits_single_terminal_plus_commit(tmp_path):
    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {}, {})
    await queue.get()  # turn_accepted
    await manager.cancel(turn_id)
    interrupted = await queue.get()
    assert interrupted.event_type == StreamEventType.TURN_INTERRUPTED
    handle = await manager.finalize(session_id, turn_id)
    assert handle.status == "pending"
    commit = await queue.get()
    assert commit.event_type == StreamEventType.COMMIT_FINAL
    assert commit.payload["authoritative"] is True


@pytest.mark.asyncio
async def test_manager_commit_fail_closed_outcome(tmp_path):
    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {}, {})
    await queue.get()  # accepted
    context = await manager.create_context(session_id, turn_id)
    await context.request_commit(CommitIntent(type="decision", ref="fail_closed:tool-side-effect"))
    await manager.finalize(session_id, turn_id)
    await queue.get()  # turn_final
    commit = await queue.get()
    assert commit.event_type == StreamEventType.COMMIT_FINAL
    assert commit.payload["commit_outcome"] == "fail_closed"
    assert commit.payload["issues"] == ["tool-side-effect"]
