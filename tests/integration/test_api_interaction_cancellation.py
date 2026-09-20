"""Layer: integration. Cancellation claims follow real session state and durable records."""
import asyncio
import os

import httpx
import pytest

from orket.interfaces.api import create_api_app

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    return create_api_app(project_root=tmp_path, environment={**os.environ, "ORKET_API_KEY": "expected", "ORKET_STREAM_EVENTS_V1": "true"})


async def _cancel(app, session_id, turn_id=None):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app, raise_app_exceptions=False),
                                base_url="http://fixture") as client:
        return await client.post(
            f"/v1/interactions/{session_id}/cancel", json={"turn_id": turn_id},
            headers={"X-API-Key": "expected"},
        )


@pytest.mark.parametrize("target", ["missing-session", "missing-turn", "idle", "foreign-turn", "session-as-turn", "finalized"])
async def test_cancel_rejects_unobserved_or_foreign_effect(tmp_path, monkeypatch, target):
    app = _app(tmp_path, monkeypatch)
    async with app.router.lifespan_context(app):
        owner = app.state.api_runtime_context
        manager = owner.interaction_manager
        session_id = await manager.start({})
        turn_id, queue = None, None
        try:
            if target == "missing-session":
                session_id = "does-not-exist"
            elif target == "missing-turn":
                turn_id = "does-not-exist"
            elif target in {"foreign-turn", "finalized", "session-as-turn"}:
                actual_session = await manager.start({}) if target == "foreign-turn" else session_id
                queue = await manager.bus.subscribe(actual_session)
                turn_id = await manager.begin_turn(actual_session, {}, {})
                await queue.get()
                if target == "finalized":
                    await manager.finalize(session_id, turn_id)
                elif target == "session-as-turn":
                    turn_id = session_id
            response = await _cancel(app, session_id, turn_id)
            assert response.status_code == (409 if target in {"idle", "finalized"} else 404)
            target_ref = f"interaction-turn:{turn_id}" if turn_id else f"interaction-session:{session_id}"
            assert await owner.engine.control_plane_repository.list_operator_actions(target_ref=target_ref) == []
            if target in {"foreign-turn", "session-as-turn"}:
                assert queue.empty()
                detail = await manager.queries.get_session_replay_timeline(actual_session)
                assert detail["turns"][-1]["terminal_event"] is None
        finally:
            await owner.close()


@pytest.mark.parametrize("turn_scope", [False, True])
async def test_cancel_publishes_once_after_real_transition(tmp_path, monkeypatch, turn_scope):
    app = _app(tmp_path, monkeypatch)
    async with app.router.lifespan_context(app):
        owner = app.state.api_runtime_context
        manager = owner.interaction_manager
        session_id = await manager.start({})
        queue = await manager.bus.subscribe(session_id)
        turn_id = await manager.begin_turn(session_id, {}, {})
        await queue.get()
        target = turn_id if turn_scope else session_id
        try:
            response = await _cancel(app, session_id, turn_id if turn_scope else None)
            assert response.status_code == 200 and response.json() == {"ok": True, "target": target}
            event = await asyncio.wait_for(queue.get(), 1)
            assert event.event_type.value == "turn_interrupted" and event.turn_id == turn_id
            repeated = await _cancel(app, session_id, turn_id if turn_scope else None)
            assert repeated.status_code == 409 and queue.empty()
            target_ref = f"interaction-turn:{target}" if turn_scope else f"interaction-session:{target}"
            records = await owner.engine.control_plane_repository.list_operator_actions(target_ref=target_ref)
            assert len(records) == 1 and records[0].result == "accepted_cancel"
            assert records[0].receipt_refs == [f"interaction-cancel:{turn_id}"]
        finally:
            await owner.close()
