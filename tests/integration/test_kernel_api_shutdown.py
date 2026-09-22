"""Layer: integration. Authenticated in-process HTTP shutdown drains Kernel publication."""

import asyncio
import json
from pathlib import Path

import aiosqlite
import httpx
import pytest

from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime
from tests.helpers.kernel_state_probe import kernel_app
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.integration.test_kernel_publication_input_capture import hold_first_lookup

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("credential_runtime")]


async def test_authenticated_kernel_request_shutdown_drains_sqlite_publication(tmp_path, monkeypatch):
    app = kernel_app(tmp_path)
    async with app.router.lifespan_context(app):
        owner = app.state.api_runtime_context
        engine = owner.engine
        database = Path(engine.control_plane_execution_repository.db_path)
        entered, release = hold_first_lookup(monkeypatch, engine.control_plane_execution_repository)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as client:
            request = asyncio.create_task(
                client.post(
                    "/v1/kernel/admit-proposal",
                    headers={"X-API-Key": TEST_API_KEY},
                    json={
                        "session_id": "shutdown-owned",
                        "trace_id": "trace",
                        "proposal": {"proposal_type": "action.tool_call", "payload": {"tool_name": "local.echo"}},
                    },
                )
            )
            closing = None
            try:
                await asyncio.wait_for(entered.wait(), 10)
                closing = asyncio.create_task(owner.close())
                await asyncio.sleep(0.02)
                assert not closing.done() and not owner.closed and not request.done()
                release.set()
                response = await asyncio.wait_for(request, 10)
                await asyncio.wait_for(closing, 10)
                assert response.status_code == 503 and owner.closed
                async with aiosqlite.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
                    rows = await (await connection.execute("SELECT payload_json FROM control_plane_runs")).fetchall()
                assert any(json.loads(row[0])["run_id"] == "kernel-action-run:shutdown-owned:trace" for row in rows)
            finally:
                release.set()
                await asyncio.gather(request, *([closing] if closing else []), return_exceptions=True)
