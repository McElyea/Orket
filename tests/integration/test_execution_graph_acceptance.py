"""Authenticated graph reads distinguish lifecycle from retained card acceptance."""
from __future__ import annotations

import asyncio
import json

import aiosqlite
import httpx
import pytest

from orket.adapters.storage.card_migrations import CARD_BOOTSTRAP_MIGRATIONS
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime import create_api_app
from orket.runtime.policy.composition import CompositionConfig
from orket.schema import CardStatus
from tests.helpers.card_completion import complete_existing_card

pytestmark = pytest.mark.integration


async def graph_runtime(root, case):
    db = root / "cards.db"
    if case == "legacy_done":
        async with aiosqlite.connect(db) as conn:
            await SQLiteMigrationRunner(namespace="card_repository").apply(conn, CARD_BOOTSTRAP_MIGRATIONS)
            await conn.execute("INSERT INTO issues (id, summary, seat, type, priority, status, build_id, session_id) "
                               "VALUES ('ROOT', 'Historical work', 'developer', 'issue', 2.0, 'done', 'build', 'GRAPH')")
            await conn.execute("PRAGMA user_version=1")
            await conn.commit()
    engine = await asyncio.to_thread(OrchestrationEngine, workspace_root=root / "workspace",
                                     db_path=str(db), config_root=root)
    app = await asyncio.to_thread(create_api_app, CompositionConfig(project_root=root))
    context = app.state.api_runtime_context
    await context.engine.close()
    context.engine = engine
    await engine.sessions.start_session("GRAPH", {"type":"epic", "name":"Graph", "department":"core", "task_input":"probe"})
    if case not in {"legacy_done", "missing"}:
        await engine.cards.save({"id":"ROOT", "summary":"Prerequisite", "seat":"developer",
                                 "build_id":"foreign" if case == "foreign_build" else "build",
                                 "session_id":"OUTSIDE" if case == "outside_view" else "GRAPH"})
        service = engine.runtime_context.card_completion
        await complete_existing_card(engine.cards, "ROOT", service.workspace_root, service=service,
                                     target_status=CardStatus.GUARD_APPROVED if case == "guard_approved" else CardStatus.DONE)
        if case in {"archived", "canceled"}:
            await engine.cards.update_status("ROOT", CardStatus(case))
        if case == "missing_evidence":
            await asyncio.to_thread(service.acceptance.evidence_store.db_path.unlink)
    await engine.cards.save({"id":"CHILD", "summary":"Dependent", "seat":"developer", "build_id":"build",
                             "session_id":"GRAPH", "depends_on":["ROOT"]})
    return app, engine


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["done", "guard_approved", "archived", "canceled", "legacy_done", "missing",
                                  "missing_evidence", "foreign_build", "outside_view"])
# Layer: integration
async def test_graph_dependency_labels_require_current_retained_acceptance(tmp_path, monkeypatch, case):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    app, _ = await graph_runtime(tmp_path, case)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/runs/GRAPH/execution-graph", headers={"X-API-Key":"test-key"})
        assert response.status_code == 200, response.text
        nodes = {node["id"]:node for node in response.json()["nodes"]}
        accepted = case in {"done", "guard_approved", "outside_view"}
        assert nodes["CHILD"]["blocked"] is (not accepted)
        assert nodes["CHILD"]["blocked_by"] == ([] if accepted else ["ROOT"])
        child = nodes["CHILD"]
        assert set(child["accepted_dependency_receipts"]) == ({"ROOT"} if accepted else set())
        assert set(child["dependency_rejections"]) == (set() if accepted else {"ROOT"})
        assert child["unresolved_dependencies"] == (["ROOT"] if case in {"missing", "outside_view"} else [])
        if "ROOT" in nodes:
            root = nodes["ROOT"]
            retained = case in {"done", "guard_approved", "foreign_build"}
            assert root["completion_accepted"] is retained
            assert bool(root["completion_ref"]) is retained
            assert bool(root["completion_rejection"]) is (not retained)
    finally:
        await app.state.api_runtime_context.close()


@pytest.mark.asyncio
# Layer: integration
async def test_graph_rechecks_evidence_on_each_read_and_persists_observed_projection(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    app, engine = await graph_runtime(tmp_path, "done")
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"X-API-Key": "test-key"}) as client:
            first = await client.get("/v1/runs/GRAPH/execution-graph")
            assert first.status_code == 200
            assert first.json()["nodes"][0]["completion_accepted"] is True
            evidence = engine.runtime_context.card_completion.acceptance.evidence_store.db_path
            await asyncio.to_thread(evidence.unlink)
            second = await client.get("/v1/runs/GRAPH/execution-graph")
        assert second.status_code == 200
        nodes = {node["id"]: node for node in second.json()["nodes"]}
        assert nodes["ROOT"]["status"] == "done"
        assert nodes["ROOT"]["completion_accepted"] is False
        assert nodes["CHILD"]["blocked_by"] == ["ROOT"]
        snapshots = await asyncio.to_thread(lambda: list(tmp_path.rglob("execution_graph_snapshot.json")))
        assert len(snapshots) == 1
        assert json.loads(await asyncio.to_thread(snapshots[0].read_text, encoding="utf-8")) == second.json()
        assert not await asyncio.to_thread(evidence.exists)
    finally:
        await app.state.api_runtime_context.close()


@pytest.mark.asyncio
# Layer: integration
async def test_graph_reports_dependency_cycle_without_changing_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    app, engine = await graph_runtime(tmp_path, "missing")
    try:
        await engine.cards.save({"id": "ROOT", "summary": "Cycle", "seat": "developer", "build_id": "build",
                                 "session_id": "GRAPH", "depends_on": ["CHILD"]})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/runs/GRAPH/execution-graph", headers={"X-API-Key": "test-key"})
        assert response.status_code == 200
        graph = response.json()
        assert graph["has_cycle"] is True
        assert set(graph["cycle_nodes"]) == {"ROOT", "CHILD"}
        assert graph["execution_order"] == []
        assert all(node["blocked"] and node["status"] == "ready" for node in graph["nodes"])
    finally:
        await app.state.api_runtime_context.close()


@pytest.mark.asyncio
# Layer: integration
async def test_graph_terminal_lifecycle_does_not_hide_rejected_dependencies(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    app, engine = await graph_runtime(tmp_path, "missing")
    try:
        service = engine.runtime_context.card_completion
        await complete_existing_card(engine.cards, "CHILD", service.workspace_root, service=service)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/runs/GRAPH/execution-graph", headers={"X-API-Key": "test-key"})
        assert response.status_code == 200
        child, = response.json()["nodes"]
        assert child["status"] == "done"
        assert child["completion_accepted"] is True
        assert child["blocked"] is True
        assert child["blocked_by"] == ["ROOT"]
    finally:
        await app.state.api_runtime_context.close()


@pytest.mark.asyncio
# Layer: integration
async def test_graph_handoffs_remain_observations_and_snapshot_failure_is_logged(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    app, _ = await graph_runtime(tmp_path, "done")
    try:
        run_path = tmp_path / "workspace" / "runs" / "GRAPH"
        await asyncio.to_thread((run_path / "agent_output").mkdir, parents=True)
        await asyncio.to_thread((run_path / "agent_output" / "observability").write_text, "obstruction", encoding="utf-8")
        records = [{"event": "turn_complete", "data": {"runtime_event": {
            "session_id": "GRAPH", "issue_id": card_id, "turn_index": turn}}}
            for turn, card_id in enumerate(["CHILD", "ROOT", "CHILD", "ROOT"])]
        await asyncio.to_thread((run_path / "orket.log").write_text,
                               "\n".join(json.dumps(row) for row in records), encoding="utf-8")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/runs/GRAPH/execution-graph", headers={"X-API-Key": "test-key"})
        assert response.status_code == 200
        graph = response.json()
        assert graph["execution_order"] == ["ROOT", "CHILD"]
        assert graph["has_cycle"] is False
        assert graph["edge_count"] == 3
        assert [edge["kind"] for edge in graph["edges_detailed"]] == ["depends_on", "handoff", "handoff"]
        assert graph["nodes"][1]["completion_accepted"] is False
        assert "Execution graph snapshot persistence failed for session GRAPH" in caplog.text
    finally:
        await app.state.api_runtime_context.close()
