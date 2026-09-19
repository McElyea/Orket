"""Captured identities, clocks and nested inputs at actual interaction transitions."""
import asyncio
from itertools import repeat

import pytest

from orket.application.interactions.commit import CommitOrchestrator
from orket.application.interactions.manager import InteractionManager
from orket.core.contracts.interaction_stream import StreamEventType
from orket.streaming.bus import StreamBus
from tests.integration.test_interaction_transition_lifetime import hold_event

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
STAMP = "2026-09-19T10:00:00+00:00"


class Inputs:
    def __init__(self, identities):
        self.identities, self.stamp = iter(identities), STAMP

    def create_effect_owner_id(self):
        return next(self.identities)

    def utc_now_iso(self):
        return self.stamp

    def monotonic_ns(self):
        return 321_000_000


def make_owner(root, inputs, **kwargs):
    return InteractionManager(bus=StreamBus(), commit_orchestrator=CommitOrchestrator(project_root=root),
                              project_root=root, inputs=inputs, **kwargs)


async def test_reused_identity_refuses_without_abandoning_existing_session_or_turn(tmp_path):
    manager = make_owner(tmp_path, Inputs(repeat("one-id")))
    session = await manager.start({"retained": True})
    try:
        with pytest.raises(ValueError, match="E_INTERACTION_SESSION_ADMISSION"):
            await manager.start({"retained": False})
        turn = await manager.begin_turn(session)
        with pytest.raises(ValueError, match="active turn"):
            await manager.begin_turn(session)
        assert (await manager.queries.get_session_detail(session))["session_params"] == {"retained": True}
        assert (await manager.queries.get_session_status(session))["status"] == "active"
        await manager.finalize(session, turn)
        with pytest.raises(ValueError, match="E_INTERACTION_TURN_ID_REUSED"):
            await manager.begin_turn(session)
        assert (await manager.queries.get_session_status(session))["status"] == "idle"
    finally:
        await manager.aclose()


async def test_admission_captures_nested_values_and_time_before_publication(tmp_path, monkeypatch):
    inputs = Inputs(["session", "turn"])
    manager = make_owner(tmp_path, inputs)
    original = {"npc": {"name": "original"}}
    session = await manager.start(original)
    original["npc"]["name"] = "changed"
    queue = await manager.bus.subscribe(session)
    entered, release = hold_event(monkeypatch, manager.bus, StreamEventType.TURN_ACCEPTED)
    payload, params = {"text": ["original"]}, {"persona": ["original"]}
    task = asyncio.create_task(manager.begin_turn(session, payload, params,
                               context_inputs={"input_config": payload, "turn_params": params}))
    try:
        await asyncio.wait_for(entered.wait(), 0.5)
        payload["text"].append("changed")
        params["persona"].append("changed")
        inputs.stamp = "2030-01-01T00:00:00+00:00"
        release.set()
        turn = await asyncio.wait_for(task, 3)
        event = await queue.get()
        assert event.payload["input"] == {"text": ["original"]}
        assert event.payload["turn_params"] == {"persona": ["original"]}
        context = await manager.create_context(session, turn)
        assert context.session_params() == {"npc": {"name": "original"}}
        assert context.packet1_context()["input_config"] == {"text": ["original"]}
        row = (await manager.queries.get_session_replay_timeline(session))["turns"][0]
        assert row["accepted_at"] == STAMP
        assert (await manager.finalize(session, turn)).requested_at_mono_ts_ms == 321
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await manager.aclose()
        await manager.bus.unsubscribe(session, queue)


async def test_interrupted_session_start_unregisters_after_retained_hook(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()
    registered = set()

    async def started(session):
        entered.set()
        await release.wait()
        registered.add(session)

    async def closed(session):
        registered.remove(session)

    manager = make_owner(tmp_path, Inputs(["session"]), on_session_started=started, on_session_closed=closed)
    task = asyncio.create_task(manager.start({}))
    try:
        await asyncio.wait_for(entered.wait(), 0.5)
        task.cancel()
        await asyncio.sleep(0.02)
        task.cancel()
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert not registered and await manager.queries.get_session_detail("session") is None
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await manager.aclose()


@pytest.mark.parametrize("event_type,payload", [
    (StreamEventType.COMMIT_FINAL, {}), (StreamEventType.TURN_FINAL, {}),
    (StreamEventType.TOKEN_DELTA, {"authoritative": True}),
])
async def test_workload_context_cannot_publish_lifecycle_or_authority_claims(tmp_path, event_type, payload):
    manager = make_owner(tmp_path, Inputs(["session", "turn"]))
    session = await manager.start({})
    turn = await manager.begin_turn(session)
    context = await manager.create_context(session, turn)
    queue = await manager.bus.subscribe(session)
    try:
        with pytest.raises(ValueError, match="E_INTERACTION_"):
            await context.emit_event(event_type, payload)
        assert queue.empty()
        assert (await manager.queries.get_session_status(session))["status"] == "active"
    finally:
        await manager.aclose()
        await manager.bus.unsubscribe(session, queue)
