"""Layer: integration. Real SQLite commits and cleanup retained through interruption."""
import asyncio
from contextlib import asynccontextmanager

import aiosqlite
import httpx
import pytest

import orket.adapters.storage.async_flow_repository as storage
from orket.interfaces.api import create_api_app
from tests.helpers.flow_authoring import FlowInputs, definition, service

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def interrupt_twice(task):
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    responsive = asyncio.Event()
    asyncio.get_running_loop().call_soon(responsive.set)
    await asyncio.wait_for(responsive.wait(), 0.5)


@pytest.mark.parametrize("cleanup_failure", [False, True])
async def test_cancelled_create_retains_real_commit_and_connection_cleanup(tmp_path, monkeypatch, cleanup_failure):
    entered, release, closed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_commit, connect = aiosqlite.Connection.commit, storage.connect_sqlite_wal

    async def held_commit(conn):
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        await original_commit(conn)

    @asynccontextmanager
    async def observed_connection(path):
        async with connect(path) as conn:
            yield conn
        closed.set()
        if cleanup_failure:
            raise OSError("injected post-close failure")

    repo = storage.AsyncFlowRepository(tmp_path / "original" / "flow.sqlite3")
    with monkeypatch.context() as patch:
        patch.setattr(aiosqlite.Connection, "commit", held_commit)
        patch.setattr(storage, "connect_sqlite_wal", observed_connection)
        task = asyncio.create_task(service(repo).create_flow(definition()))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            repo.db_path = str(tmp_path / "changed" / "flow.sqlite3")
            await interrupt_twice(task)
            assert not closed.is_set()
        finally:
            release.set()
            with pytest.raises(OSError if cleanup_failure else asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
        assert closed.is_set()
    row = await storage.AsyncFlowRepository(tmp_path / "original" / "flow.sqlite3").get_flow("FLOW-FIXED")
    assert row["name"] == "original"
    assert not (tmp_path / "changed").exists()


async def test_create_captures_payload_before_storage_admission(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()

    class HeldRepository(storage.AsyncFlowRepository):
        async def _ensure_initialized(self, conn):
            await super()._ensure_initialized(conn)
            entered.set()
            await asyncio.wait_for(release.wait(), 5)

    repo = HeldRepository(tmp_path / "flow.sqlite3")
    payload = definition().model_dump()
    task = asyncio.create_task(repo.create_flow(
        flow_id="FLOW-FIXED", revision_id="frv_1", name="original", description="input",
        payload=payload, created_at="captured", updated_at="captured",
    ))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        payload["nodes"][1]["label"] = "changed"
    finally:
        release.set()
        assert await asyncio.wait_for(task, 5)
    assert (await repo.get_flow("FLOW-FIXED"))["payload"]["nodes"][1]["label"] == "Card"


async def test_application_close_waits_for_cancelled_flow_commit(tmp_path, monkeypatch):
    entered, release, settled = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original = storage.AsyncFlowRepository._execute

    async def held_execute(repo, operation, **kwargs):
        async def held_operation(conn):
            result = await operation(conn)
            entered.set()
            await asyncio.wait_for(release.wait(), 5)
            return result

        try:
            return await original(repo, held_operation, **kwargs)
        finally:
            settled.set()

    app = create_api_app(project_root=tmp_path, environment={"ORKET_API_KEY": "flow-proof"}, runtime_inputs=FlowInputs())
    context = app.state.api_runtime_context
    with monkeypatch.context() as patch:
        patch.setattr(storage.AsyncFlowRepository, "_execute", held_execute)
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                request = asyncio.create_task(client.post("/v1/flows", headers={"X-API-Key": "flow-proof"},
                                                          json={"definition": definition().model_dump()}))
                await asyncio.wait_for(entered.wait(), 5)
                close = asyncio.create_task(context.close())
                try:
                    await interrupt_twice(request)
                    assert not close.done() and not settled.is_set()
                finally:
                    release.set()
                    response = await asyncio.wait_for(request, 5)
                    assert response.status_code == 503
                    assert response.json() == {"detail": "API runtime is closing."}
                    await asyncio.wait_for(close, 5)
        finally:
            release.set()
            await context.close()
    assert context.closed and settled.is_set()
    repo = storage.AsyncFlowRepository(tmp_path / ".orket/durable/db/orket_ui_flows.sqlite3")
    assert (await repo.get_flow("FLOW-FIXED"))["name"] == "original"
