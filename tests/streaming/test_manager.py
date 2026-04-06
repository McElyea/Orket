from __future__ import annotations

import pytest

from orket.streaming import CommitOrchestrator, InteractionManager, StreamBus
from orket.streaming.contracts import CommitIntent, StreamEventType


@pytest.mark.asyncio
async def test_manager_begin_turn_emits_turn_accepted_and_linear_policy(tmp_path):
    """Layer: unit. Verifies interaction manager enforces linear turns and emits turn acceptance."""
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
    """Layer: unit. Verifies cancel then finalize emits one terminal event and one authoritative commit result."""
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
    """Layer: unit. Verifies interaction manager preserves fail-closed commit outcomes."""
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


@pytest.mark.asyncio
async def test_commit_orchestrator_persists_authority_artifact(tmp_path):
    """Layer: integration. Verifies commit orchestration persists the authoritative artifact on disk."""
    orchestrator = CommitOrchestrator(project_root=tmp_path)

    outcome = await orchestrator.commit(
        session_id="session-1",
        turn_id="turn-1",
        intents=[CommitIntent(type="turn_finalize", ref="turn-1")],
    )

    authority_path = (
        tmp_path / "workspace" / "interactions" / "session-1" / "turn-1" / "authority_commit.json"
    )
    assert authority_path.exists()
    assert outcome["authoritative"] is True


@pytest.mark.asyncio
async def test_manager_session_snapshot_and_replay_expose_context_lineage(tmp_path):
    """Layer: unit. Verifies interaction manager exposes explicit session-context envelope and provider lineage."""
    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({"npc": "guard", "tone": "calm"})
    turn_id = await manager.begin_turn(
        session_id,
        {"seed": 5},
        {"persona": "reviewer"},
        context_inputs={
            "input_config": {"seed": 5},
            "turn_params": {"persona": "reviewer"},
            "workload_id": "stream_test_v1",
            "department": "core",
            "workspace": str((tmp_path / "workspace" / "default").resolve()),
        },
    )

    context = await manager.create_context(session_id, turn_id)
    assert context.packet1_context() == {
        "session_params": {"npc": "guard", "tone": "calm"},
        "input_config": {"seed": 5},
        "turn_params": {"persona": "reviewer"},
        "workload_id": "stream_test_v1",
        "department": "core",
        "workspace": str((tmp_path / "workspace" / "default").resolve()),
    }
    assert context.packet1_context_envelope() == {
        "context_version": "packet1_session_context_v1",
        "continuity": {
            "session_id": session_id,
            "session_params": {"npc": "guard", "tone": "calm"},
        },
        "turn_request": {
            "input_config": {"seed": 5},
            "turn_params": {"persona": "reviewer"},
            "workload_id": "stream_test_v1",
            "department": "core",
            "workspace": str((tmp_path / "workspace" / "default").resolve()),
        },
        "extension_manifest": {},
    }
    assert [row["provider_id"] for row in context.packet1_provider_lineage()] == [
        "host_continuity",
        "turn_request",
        "extension_manifest_required_capabilities",
    ]

    detail = await manager.get_session_detail(session_id)
    assert detail is not None
    assert detail["surface"] == "interaction_session"
    assert detail["turn_count"] == 1

    snapshot = await manager.get_session_snapshot(session_id)
    assert snapshot is not None
    assert snapshot["session_context_pipeline"]["context_version"] == "packet1_session_context_v1"
    assert snapshot["session_context_pipeline"]["latest_context_envelope"]["turn_request"]["workload_id"] == "stream_test_v1"
    assert snapshot["replay_boundary"]["timeline_view"] == "inspection_only"

    replay = await manager.get_session_replay_timeline(session_id)
    assert replay is not None
    assert replay["turn_count"] == 1
    assert replay["turns"][0]["turn_index"] == 1
    assert replay["turns"][0]["context_envelope"]["continuity"]["session_id"] == session_id
