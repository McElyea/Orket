"""Real interaction state, stream queues and commit files under interruption."""
from __future__ import annotations

import asyncio
import json

import pytest

from orket.application.interactions.commit import CommitOrchestrator
from orket.application.interactions.manager import InteractionManager
from orket.core.contracts.interaction_stream import StreamEventType
from orket.streaming import StreamBus

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def owner(root):
    bus = StreamBus()
    manager = InteractionManager(stream_enabled=True, bus=bus, commit_orchestrator=CommitOrchestrator(project_root=root), project_root=root)
    return manager, bus


def hold_event(monkeypatch, bus, event_type):
    entered, release = asyncio.Event(), asyncio.Event()
    publish = bus.publish

    async def held(**kwargs):
        if kwargs["event_type"] == event_type:
            entered.set()
            await release.wait()
        return await publish(**kwargs)

    monkeypatch.setattr(bus, "publish", held)
    return entered, release


async def test_interrupted_admission_drains_and_closes_unadopted_turn(tmp_path, monkeypatch):
    manager, bus = owner(tmp_path)
    session = await manager.start({})
    queue = await manager.bus.subscribe(session)
    entered, release = hold_event(monkeypatch, bus, StreamEventType.TURN_ACCEPTED)
    task = asyncio.create_task(manager.begin_turn(session, {"text": "unadopted"}))
    try:
        await asyncio.wait_for(entered.wait(), 0.5)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        status = await manager.queries.get_session_status(session)
        assert status["status"] == "idle"
        events = [queue.get_nowait() for _ in range(queue.qsize())]
        assert [event.event_type for event in events] == [
            StreamEventType.TURN_ACCEPTED, StreamEventType.TURN_INTERRUPTED, StreamEventType.COMMIT_FINAL,
        ]
        assert events[-1].payload["commit_outcome"] == "fail_closed"
        assert events[-1].payload["issues"] == ["admission_interrupted"]
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await manager.close(session)
        await bus.unsubscribe(session, queue)


async def test_interrupted_finalization_drains_to_real_commit(tmp_path, monkeypatch):
    manager, bus = owner(tmp_path)
    session = await manager.start({})
    turn = await manager.begin_turn(session)
    entered, release = hold_event(monkeypatch, bus, StreamEventType.TURN_FINAL)
    task = asyncio.create_task(manager.finalize(session, turn))
    try:
        await asyncio.wait_for(entered.wait(), 0.5)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        await manager.finalize(session, turn)
        path = tmp_path / "workspace/interactions" / session / turn / "authority_commit.json"
        payload = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
        assert payload["authoritative"] and payload["turn_id"] == turn
        assert (await manager.queries.get_session_status(session))["status"] == "idle"
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await manager.close(session)


async def test_concurrent_finalizers_wait_for_one_observed_transition(tmp_path, monkeypatch):
    manager, bus = owner(tmp_path)
    session = await manager.start({})
    queue = await manager.bus.subscribe(session)
    turn = await manager.begin_turn(session)
    await queue.get()
    entered, release = hold_event(monkeypatch, bus, StreamEventType.TURN_FINAL)
    first = asyncio.create_task(manager.finalize(session, turn))
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 0.5)
        second = asyncio.create_task(manager.finalize(session, turn))
        await asyncio.sleep(0.02)
        assert not first.done() and not second.done()
        release.set()
        await asyncio.wait_for(asyncio.gather(first, second), 3)
        events = [queue.get_nowait() for _ in range(queue.qsize())]
        assert [event.event_type for event in events] == [StreamEventType.TURN_FINAL, StreamEventType.COMMIT_FINAL]
    finally:
        release.set()
        await asyncio.gather(*[task for task in (first, second) if task is not None], return_exceptions=True)
        await manager.close(session)
        await bus.unsubscribe(session, queue)


async def test_failed_finalization_remains_a_failure_on_retry(tmp_path, monkeypatch):
    manager, _ = owner(tmp_path)
    session = await manager.start({})
    turn = await manager.begin_turn(session)

    async def fail(**kwargs):
        raise OSError("fixture commit storage unavailable")

    monkeypatch.setattr(manager.commit_orchestrator, "commit", fail)
    try:
        for _ in range(2):
            with pytest.raises(OSError, match="fixture commit storage unavailable"):
                await manager.finalize(session, turn)
    finally:
        # Failed durable effects do not establish a clean close; retain the error.
        await asyncio.gather(manager.close(session), return_exceptions=True)
