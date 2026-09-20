"""Layer: integration. Real SQLite authoring through services and authenticated ASGI."""
import asyncio
import os
from contextlib import asynccontextmanager

import httpx
import pytest

from orket.adapters.storage.async_flow_repository import AsyncFlowRepository
from orket.application.services.flow_authoring_service import FlowAuthoringConflictError
from orket.interfaces.api import create_api_app
from tests.helpers.flow_authoring import FlowInputs, definition, service

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@asynccontextmanager
async def client_for(root, inputs=None):
    app = create_api_app(project_root=root, environment={**os.environ, "ORKET_API_KEY": "flow-proof"}, runtime_inputs=inputs)
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"X-API-Key": "flow-proof"},
    ) as client:
        yield client
    assert app.state.api_runtime_context.closed and client.is_closed


async def test_concurrent_public_saves_consume_expected_revision_once(tmp_path, monkeypatch):
    reads, release = [], asyncio.Event()
    original_get = AsyncFlowRepository.get_flow

    async def held_read(repo, flow_id):
        row = await original_get(repo, flow_id)
        reads.append(row["revision_id"])
        if len(reads) == 2:
            release.set()
        await asyncio.wait_for(release.wait(), 5)
        return row

    async with client_for(tmp_path) as client:
        response = await client.post("/v1/flows", json={"definition": definition().model_dump()})
        assert response.status_code == 200
        created = response.json()
        with monkeypatch.context() as patch:
            patch.setattr(AsyncFlowRepository, "get_flow", held_read)
            responses = await asyncio.wait_for(asyncio.gather(*[
                client.put("/v1/flows/" + created["flow_id"], json={
                    "definition": definition(name).model_dump(), "expected_revision_id": created["revision_id"],
                }) for name in ("first", "second")]), 10)
        assert reads == [created["revision_id"]] * 2
        assert sorted(r.status_code for r in responses) == [200, 409]
        winner = next(i for i, r in enumerate(responses) if r.status_code == 200)
        stored = (await client.get("/v1/flows/" + created["flow_id"])).json()
        assert stored["name"] == ("first", "second")[winner]
        assert stored["revision_id"] == responses[winner].json()["revision_id"]
        assert stored["created_at"] == created["saved_at"]


async def test_save_captures_nested_definition_before_awaited_read(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()

    class HeldRepository(AsyncFlowRepository):
        async def get_flow(self, flow_id):
            row = await super().get_flow(flow_id)
            entered.set()
            await asyncio.wait_for(release.wait(), 5)
            return row

    repo = HeldRepository(tmp_path / "flow.sqlite3")
    author = service(repo)
    created = await author.create_flow(definition())
    submitted = definition("captured")
    task = asyncio.create_task(author.update_flow(flow_id=created.flow_id, definition=submitted))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        submitted.name = "changed-after-await"
        submitted.nodes[1].label = "changed-after-await"
        submitted.nodes.clear()
    finally:
        release.set()
        result = await asyncio.wait_for(task, 5)
    row = await AsyncFlowRepository(repo.db_path).get_flow(created.flow_id)
    assert row["name"] == "captured" and row["payload"]["nodes"][1]["label"] == "Card"
    assert result.validation.is_valid and row["revision_id"] == result.revision_id


async def test_public_creation_collision_preserves_original_and_captured_host_inputs(tmp_path):
    inputs = FlowInputs()
    async with client_for(tmp_path, inputs) as client:
        first = await client.post("/v1/flows", json={"definition": definition("first").model_dump()})
        second = await client.post("/v1/flows", json={"definition": definition("second").model_dump()})
        assert first.status_code == 200 and second.status_code == 409
        assert second.json()["detail"].startswith("flow_id_conflict:")
        assert first.json()["flow_id"] == "FLOW-FIXED" and first.json()["revision_id"] == "frv_1"
        assert first.json()["saved_at"] == "2026-09-18T12:00:00+00:00"
        row = (await client.get("/v1/flows/FLOW-FIXED")).json()
        assert row["name"] == "first" and row["revision_id"] == "frv_1"
        assert (await client.get("/v1/flows")).json()["count"] == 1


@pytest.mark.parametrize("guard", ["stale", ""])
async def test_explicit_stale_guard_refuses_save_and_run(tmp_path, guard):
    async with client_for(tmp_path, FlowInputs()) as client:
        assert (await client.post("/v1/flows", json={"definition": definition().model_dump()})).status_code == 200
        saved = await client.put("/v1/flows/FLOW-FIXED", json={
            "definition": definition("refused").model_dump(), "expected_revision_id": guard,
        })
        run = await client.post("/v1/flows/FLOW-FIXED/runs", json={"expected_revision_id": guard})
        assert saved.status_code == run.status_code == 409
        assert all(r.json()["detail"].startswith("revision_conflict:") for r in (saved, run))
        assert (await client.get("/v1/flows/FLOW-FIXED")).json()["name"] == "original"


async def test_unguarded_save_remains_supported_and_missing_flow_is_not_created(tmp_path):
    async with client_for(tmp_path, FlowInputs()) as client:
        body = {"definition": definition().model_dump()}
        missing = await client.put("/v1/flows/missing", json=body)
        assert missing.status_code == 404
        assert (await client.get("/v1/flows")).json()["count"] == 0
        created = (await client.post("/v1/flows", json=body)).json()
        saved = await client.put("/v1/flows/FLOW-FIXED", json={"definition": definition("updated").model_dump()})
        assert saved.status_code == 200 and saved.json()["revision_id"] != created["revision_id"]
        row = (await client.get("/v1/flows/FLOW-FIXED")).json()
        assert row["name"] == "updated" and row["created_at"] == created["saved_at"]


async def test_repeated_revision_refuses_update(tmp_path):
    inputs = FlowInputs()
    author = service(AsyncFlowRepository(tmp_path / "flow.sqlite3"), inputs)
    first = await author.create_flow(definition())
    inputs.revision_calls = 0
    with pytest.raises(FlowAuthoringConflictError, match="revision_conflict"):
        await author.update_flow(flow_id=first.flow_id, definition=definition("refused"))
    assert (await author.get_flow(first.flow_id))["name"] == "original"


async def test_validation_and_auth_refusal_do_not_mint_or_persist_flows(tmp_path):
    inputs = FlowInputs()
    async with client_for(tmp_path, inputs) as client:
        body = {"definition": definition().model_dump()}
        response = await client.post("/v1/flows", json=body, headers={"X-API-Key": "incorrect"})
        assert response.status_code == 403
        valid = await client.post("/v1/flows/validate", json=body)
        assert valid.status_code == 200 and valid.json()["is_valid"]
        body["definition"]["nodes"] = []
        invalid = await client.post("/v1/flows/validate", json=body)
        assert invalid.status_code == 200 and not invalid.json()["is_valid"]
        assert inputs.flow_calls == inputs.revision_calls == 0
        assert not (tmp_path / ".orket/durable/db/orket_ui_flows.sqlite3").exists()


async def test_flow_roots_are_isolated_and_invalid_drafts_persist_without_run(tmp_path):
    async with client_for(tmp_path / "first", FlowInputs()) as first, client_for(tmp_path / "second") as second:
        draft = definition()
        draft.nodes.clear()
        created = await first.post("/v1/flows", json={"definition": draft.model_dump()})
        assert created.status_code == 200 and not created.json()["validation"]["is_valid"]
        assert (await second.get("/v1/flows/FLOW-FIXED")).status_code == 404
        run = await first.post("/v1/flows/FLOW-FIXED/runs", json={})
        assert run.status_code == 409 and run.json()["detail"] == "flow_validation_failed"
