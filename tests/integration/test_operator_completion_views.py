"""Operator views require current receipts, not lifecycle or attribution claims."""
from __future__ import annotations

import asyncio
import hashlib
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from orket.application.services.card_completion_outcome_service import inspect_build_completion
from orket.application.services.run_ledger_summary_projection import validated_run_ledger_record_projection
from orket.runtime.run_summary import build_run_summary_payload
from orket.schema import CardStatus
from tests.helpers.card_completion import complete_existing_card, write_completion_source
from tests.integration.test_execution_graph_acceptance import graph_runtime

pytestmark = pytest.mark.integration


@asynccontextmanager
async def operator_runtime(root, case, *, retain_outcome=True):
    async with graph_runtime(root, case) as (app, engine):
        service = engine.runtime_context.card_completion
        await complete_existing_card(engine.cards, "CHILD", service.workspace_root, service=service)
        outcome = await inspect_build_completion(cards=engine.cards, build_id="build", expected_card_ids=("ROOT", "CHILD"))
        artifacts = {"card_completion_outcome": outcome.to_artifact(), "packet2_facts": {"source_attribution": {
            "mode": "required", "high_stakes": False, "synthesis_status": "verified",
            "artifact_provenance_verified": True, "receipt_artifact_path": "agent_output/source_attribution_receipt.json"}}}
        if not retain_outcome:
            artifacts.pop("card_completion_outcome")
        summary = build_run_summary_payload(run_id="GRAPH", status="done", failure_reason=None,
            started_at="2026-09-12T12:00:00+00:00", ended_at="2026-09-12T12:00:05+00:00", tool_names=[], artifacts=artifacts)
        await engine.run_ledger.start_run(session_id="GRAPH", run_type="epic", run_name="operator-proof",
                                        department="core", build_id="build", summary={}, artifacts={})
        await engine.run_ledger.finalize_run(session_id="GRAPH", status="done", summary=summary, artifacts=artifacts)
        await engine.sessions.complete_session("GRAPH", "done", [])
        yield app, engine


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["done", "guard_approved", "archived", "canceled", "legacy_done", "missing",
                                  "missing_evidence", "foreign_build", "outside_view"])
# Layer: integration
async def test_operator_card_and_run_views_require_retained_acceptance(tmp_path, monkeypatch, case):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    async with operator_runtime(tmp_path, case) as (app, _):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"X-API-Key": "test-key"}) as client:
            run = await client.get("/v1/runs/GRAPH/view")
            history = await client.get("/v1/runs/view")
            completed = await client.get("/v1/cards/view?filter=completed")
            card = await client.get("/v1/cards/ROOT/view") if case != "missing" else None
        assert run.status_code == history.status_code == completed.status_code == 200
        accepted = case in {"done", "guard_approved", "outside_view"}
        assert (run.json()["verification"]["status"] == "verified") is accepted
        assert (history.json()["items"][0]["verification_status"] == "verified") is accepted
        if card is not None:
            assert card.status_code == 200
            card_accepted = case in {"done", "guard_approved", "foreign_build", "outside_view"}
            assert (card.json()["filter_bucket"] == "completed") is card_accepted
            assert ("ROOT" in {item["card_id"] for item in completed.json()["items"]}) is card_accepted
            assert card.json()["completion_accepted"] is card_accepted
            assert not card.json()["raw_status"].startswith("cardstatus.")
        assert run.json()["completion_accepted"] is accepted
        assert run.json()["source_attribution"]["synthesis_status"] == "verified"


@pytest.mark.asyncio
# Layer: integration
async def test_operator_inspection_preserves_stores_and_does_not_rerun_workspace_code(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    async with operator_runtime(tmp_path, "done") as (app, engine):
        service = engine.runtime_context.card_completion
        paths = {Path(engine.cards.db_path), Path(engine.run_ledger.db_path), service.acceptance.evidence_store.db_path}

        def store_hashes():
            return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}

        before = await asyncio.to_thread(store_hashes)
        await write_completion_source(service.workspace_root, "raise RuntimeError('must not execute on inspection')\n")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"X-API-Key": "test-key"}) as client:
            for path in ("/v1/runs/GRAPH/view", "/v1/runs/view", "/v1/cards/ROOT/view", "/v1/cards/view"):
                response = await client.get(path)
                assert response.status_code == 200
                payload = response.json()
                assert all(item["completion_accepted"] for item in payload.get("items", [payload]))
        assert await asyncio.to_thread(store_hashes) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("corruption", ["missing", "receipt", "scope", "schema", "unpublished", "failed"])
# Layer: integration
async def test_operator_views_reject_missing_or_substituted_outcome(tmp_path, monkeypatch, corruption):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    async with operator_runtime(tmp_path, "done", retain_outcome=corruption != "missing") as (app, engine):
        run = validated_run_ledger_record_projection(await engine.run_ledger.get_run("GRAPH"))
        artifacts = run["artifact_json"]
        if corruption == "missing":
            artifacts.pop("card_completion_outcome", None)
        elif corruption == "receipt":
            artifacts["card_completion_outcome"]["accepted_receipts"]["ROOT"] = "0" * 64
        elif corruption == "scope":
            artifacts["card_completion_outcome"]["build_id"] = "another-build"
        elif corruption == "schema":
            artifacts["card_completion_outcome"]["schema_version"] = "unrecognized"
        status = {"unpublished": "started", "failed": "failed"}.get(corruption, "done")
        await engine.run_ledger.finalize_run(session_id="GRAPH", status=status,
                                            summary=run["summary_json"], artifacts=artifacts)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"X-API-Key": "test-key"}) as client:
            response = await client.get("/v1/runs/GRAPH/view")
            card = await client.get("/v1/cards/ROOT/view")
        assert response.status_code == 200
        assert response.json()["completion_accepted"] is False
        assert response.json()["verification"]["status"] == "unverified"
        assert response.json()["completion_rejection"]
        assert card.status_code == 200
        assert card.json()["completion_accepted"] is True
        assert card.json()["filter_bucket"] == "completed"


@pytest.mark.asyncio
# Layer: integration
async def test_operator_card_page_offset_is_applied_once(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    async with operator_runtime(tmp_path, "done") as (app, _):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"X-API-Key": "test-key"}) as client:
            full = await client.get("/v1/cards/view?limit=2")
            page = await client.get("/v1/cards/view?limit=1&offset=1")
        assert full.status_code == page.status_code == 200
        assert len(full.json()["items"]) == 2
        assert page.json()["items"] == full.json()["items"][1:]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["evidence_loss", "reopened", "new_receipt"])
# Layer: integration
async def test_operator_views_reject_stale_published_outcome(tmp_path, monkeypatch, change):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    async with operator_runtime(tmp_path, "done") as (app, engine):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"X-API-Key": "test-key"}) as client:
            before = await client.get("/v1/runs/GRAPH/view")
            assert before.json()["verification"]["status"] == "verified"
            service = engine.runtime_context.card_completion
            if change == "evidence_loss":
                await asyncio.to_thread(service.acceptance.evidence_store.db_path.unlink)
            elif change == "reopened":
                await engine.cards.update_status("ROOT", CardStatus.READY)
            else:
                await engine.cards.update_status("ROOT", CardStatus.READY)
                await complete_existing_card(engine.cards, "ROOT", service.workspace_root, service=service)
            after = await client.get("/v1/runs/GRAPH/view")
            card = await client.get("/v1/cards/ROOT/view")
        assert after.status_code == card.status_code == 200
        assert after.json()["verification"]["status"] != "verified"
        assert (card.json()["filter_bucket"] == "completed") is (change == "new_receipt")
