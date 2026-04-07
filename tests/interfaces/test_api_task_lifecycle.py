import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

import orket.state as state_module
from orket.interfaces import api as api_module


class _FakeTarget:
    async def run(self):
        await asyncio.sleep(0.01)
        return {"ok": True}


@pytest.mark.asyncio
async def test_scheduled_task_is_removed_after_completion(fresh_runtime_state):
    session_id = "task-cleanup-test"
    await state_module.runtime_state.remove_task(session_id)

    target = _FakeTarget()
    invocation = {"method_name": "run", "args": []}
    await api_module._schedule_async_invocation_task(target, invocation, "run", session_id)

    task = await state_module.runtime_state.get_task(session_id)
    assert task is not None

    await asyncio.sleep(0.05)
    assert await state_module.runtime_state.get_task(session_id) is None


@pytest.mark.asyncio
async def test_runtime_state_tracks_multiple_tasks_per_session(fresh_runtime_state):
    """Layer: integration. Verifies one session can track and clean up multiple concurrent tasks independently."""
    session_id = "task-multi-test"
    await state_module.runtime_state.remove_task(session_id)

    task_a = asyncio.create_task(asyncio.sleep(0.05))
    task_b = asyncio.create_task(asyncio.sleep(0.05))

    await state_module.runtime_state.add_task(session_id, task_a)
    await state_module.runtime_state.add_task(session_id, task_b)

    tasks = await state_module.runtime_state.get_tasks(session_id)
    assert tasks == [task_a, task_b]

    task_a.cancel()
    task_b.cancel()
    await asyncio.gather(task_a, task_b, return_exceptions=True)

    await state_module.runtime_state.remove_task(session_id, task_a)
    remaining = await state_module.runtime_state.get_tasks(session_id)
    assert remaining == [task_b]

    await state_module.runtime_state.remove_task(session_id, task_b)
    assert await state_module.runtime_state.get_tasks(session_id) == []


@pytest.mark.asyncio
async def test_heartbeat_active_tasks_converges_after_run_active_completion(monkeypatch, fresh_runtime_state):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    session_id = "hbtask01"

    async def fake_run():
        await asyncio.sleep(0.1)
        return {"ok": True}

    monkeypatch.setattr(api_module.engine, "fake_run", fake_run, raising=False)
    monkeypatch.setattr(api_module.api_runtime_node, "create_session_id", lambda: session_id)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_run_active_invocation",
        lambda asset_id, build_id, session_id, request_type: {"method_name": "fake_run", "args": []},
    )

    transport = ASGITransport(app=api_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_response = await client.post(
            "/v1/system/run-active",
            json={"issue_id": "ISSUE-1"},
            headers={"X-API-Key": "test-key"},
        )
        assert run_response.status_code == 200
        assert run_response.json()["session_id"] == session_id

        # During execution we should see an active task.
        active_seen = False
        for _ in range(20):
            hb = await client.get("/v1/system/heartbeat", headers={"X-API-Key": "test-key"})
            assert hb.status_code == 200
            if hb.json()["active_tasks"] >= 1:
                active_seen = True
                break
            await asyncio.sleep(0.01)
        assert active_seen is True

        # After completion, active task count should converge back to zero.
        settled_zero = False
        for _ in range(40):
            hb = await client.get("/v1/system/heartbeat", headers={"X-API-Key": "test-key"})
            assert hb.status_code == 200
            if hb.json()["active_tasks"] == 0:
                settled_zero = True
                break
            await asyncio.sleep(0.01)
        assert settled_zero is True


@pytest.mark.asyncio
async def test_concurrent_run_active_task_cleanup_stress(monkeypatch, fresh_runtime_state):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    base = "hbconcur"
    counter = {"n": 0}

    async def fake_run():
        await asyncio.sleep(0.03)
        return {"ok": True}

    def _new_session_id():
        counter["n"] += 1
        return f"{base}-{counter['n']}"

    monkeypatch.setattr(api_module.engine, "fake_run", fake_run, raising=False)
    monkeypatch.setattr(api_module.api_runtime_node, "create_session_id", _new_session_id)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_run_active_invocation",
        lambda asset_id, build_id, session_id, request_type: {"method_name": "fake_run", "args": []},
    )

    transport = ASGITransport(app=api_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        requests = [
            client.post(
                "/v1/system/run-active",
                json={"issue_id": f"ISSUE-{i}"},
                headers={"X-API-Key": "test-key"},
            )
            for i in range(20)
        ]
        responses = await asyncio.gather(*requests)
        assert all(r.status_code == 200 for r in responses)

        # Let tasks settle and cleanup callbacks fire.
        await asyncio.sleep(0.3)

        hb = await client.get("/v1/system/heartbeat", headers={"X-API-Key": "test-key"})
        assert hb.status_code == 200
        assert hb.json()["active_tasks"] == 0

