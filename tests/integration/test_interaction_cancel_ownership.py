"""Layer: integration. Real stream/SQLite cancellation retains lifetime and captured inputs."""
import asyncio

import aiosqlite
import httpx
import pytest

from tests.integration.test_api_interaction_cancellation import _app, _cancel

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
RESPONSIVENESS_SECONDS = 0.5
SETTLEMENT_SECONDS = 3
CAPTURED_TIME = "2026-09-19T06:00:00+00:00"


@pytest.mark.parametrize("stage", ["event", "audit"])
@pytest.mark.parametrize("stop", ["cancel", "timeout", "shutdown"])
async def test_cancel_retains_transition_and_audit_through_interruption(tmp_path, monkeypatch, stage, stop):
    app = _app(tmp_path, monkeypatch)
    async with app.router.lifespan_context(app):
        owner = app.state.api_runtime_context
        manager, repo = owner.interaction_manager, owner.engine.control_plane_repository
        session_id = await manager.start({})
        queue = await manager.bus.subscribe(session_id)
        turn_id = await manager.begin_turn(session_id, {}, {})
        await queue.get()
        entered, release = asyncio.Event(), asyncio.Event()
        target, method = (manager.bus, "publish") if stage == "event" else (repo, "save_operator_action")
        original = getattr(target, method)

        async def held(**kwargs):
            entered.set()
            await release.wait()
            return await original(**kwargs)

        monkeypatch.setattr(target, method, held)
        monkeypatch.setattr(owner.api_runtime_host, "utc_now_iso", lambda: CAPTURED_TIME)

        async def invoke():
            if stop == "timeout":
                async with asyncio.timeout(0.2):
                    return await _cancel(app, session_id, turn_id)
            return await _cancel(app, session_id, turn_id)

        request, closing = asyncio.create_task(invoke()), None
        try:
            await asyncio.wait_for(entered.wait(), SETTLEMENT_SECONDS)
            monkeypatch.setattr(owner.api_runtime_host, "utc_now_iso", lambda: "2026-09-20T06:00:00+00:00")
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as client:
                heartbeat = await asyncio.wait_for(client.get("/v1/system/heartbeat", headers={"X-API-Key": "expected"}),
                                                   RESPONSIVENESS_SECONDS)
            assert heartbeat.status_code == 200
            duplicate = await asyncio.wait_for(_cancel(app, session_id, turn_id), RESPONSIVENESS_SECONDS)
            assert duplicate.status_code == 409
            if stop == "shutdown":
                closing = asyncio.create_task(owner.close())
            elif stop == "cancel":
                request.cancel()
                await asyncio.sleep(0)
                request.cancel()
            await asyncio.sleep(0.25 if stop == "timeout" else 0.05)
            assert not request.done(), "Cancellation escaped before its selected effect and audit settled"
            if closing is not None:
                assert not closing.done() and not owner.closed
            release.set()
            result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), SETTLEMENT_SECONDS)
            if stop == "timeout":
                assert isinstance(result, TimeoutError)
            elif stop == "cancel":
                assert isinstance(result, asyncio.CancelledError)
            else:
                assert result.status_code == 503
            records = await repo.list_operator_actions(target_ref=f"interaction-turn:{turn_id}")
            assert len(records) == 1 and records[0].timestamp == CAPTURED_TIME
            assert records[0].receipt_refs == [f"interaction-cancel:{turn_id}"]
            assert (await queue.get()).event_type.value == "turn_interrupted" and queue.empty()
            timeline = await manager.queries.get_session_replay_timeline(session_id)
            assert timeline["turns"][-1]["finalized_at"] == CAPTURED_TIME
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), SETTLEMENT_SECONDS)
            if closing is not None:
                await asyncio.wait_for(closing, SETTLEMENT_SECONDS)
            await owner.close()


async def test_sqlite_refusal_cannot_report_success_or_republish_cancel(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    async with app.router.lifespan_context(app):
        owner = app.state.api_runtime_context
        manager, repo = owner.interaction_manager, owner.engine.control_plane_repository
        session_id = await manager.start({})
        turn_id = await manager.begin_turn(session_id, {}, {})
        target_ref = f"interaction-turn:{turn_id}"
        await repo.list_operator_actions(target_ref=target_ref)  # initialize the real selected database
        async with aiosqlite.connect(repo.db_path) as connection:
            await connection.execute("""CREATE TRIGGER refuse_cancel BEFORE INSERT ON operator_action_records
                BEGIN SELECT RAISE(ABORT, 'fixture audit refusal'); END""")
            await connection.commit()
        try:
            response = await _cancel(app, session_id, turn_id)
            assert response.status_code == 500
            timeline = await manager.queries.get_session_replay_timeline(session_id)
            assert timeline["turns"][-1]["terminal_event"] == "turn_interrupted"
            assert await repo.list_operator_actions(target_ref=target_ref) == []
            repeated = await _cancel(app, session_id, turn_id)
            assert repeated.status_code == 409
            assert await repo.list_operator_actions(target_ref=target_ref) == []
        finally:
            await owner.close()
