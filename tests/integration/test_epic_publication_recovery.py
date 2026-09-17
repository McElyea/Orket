"""Restart publication against real stores without resetting accepted cards."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite
import pytest

from orket.exceptions import ExecutionFailed
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline

pytestmark = pytest.mark.integration


async def abort_publication(pipeline, db_path, stage):
    async with aiosqlite.connect(db_path) as conn:
        if stage == "snapshot":
            await pipeline.snapshots._ensure_initialized(conn)
        elif stage == "success":
            await pipeline.success._ensure_initialized(conn)
        table, operation = {
            "ledger": ("run_ledger", "UPDATE"), "session": ("sessions", "UPDATE"),
            "snapshot": ("session_snapshots", "INSERT"), "success": ("success_ledger", "INSERT"),
        }[stage]
        await conn.execute(f"CREATE TRIGGER stop_publication BEFORE {operation} ON {table} "
                           "BEGIN SELECT RAISE(ABORT, 'restart-publication-fault'); END")
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["ledger", "session", "snapshot", "success"])
# Layer: integration
async def test_restart_finishes_publication_without_redispatch(test_root, workspace, db_path, stage):
    pipeline = await publication_pipeline(test_root, workspace, db_path)

    async def execute_fixture(**_kwargs):
        await accept_publication_card(pipeline, workspace)
        await abort_publication(pipeline, db_path, stage)

    pipeline.orchestrator.execute_epic = execute_fixture
    try:
        result = await pipeline.run_epic("publication_epic", build_id="build", session_id="publication-session")
        assert result.observation == "unresolved" and not result.succeeded
        assert "restart-publication-fault" in result.reason and result.evidence_refs
        receipt = await pipeline.async_cards.read_completion_receipt("ISSUE-1")
        ledger = await pipeline.run_ledger.get_run("publication-session")
        cp_run_id = ledger["artifact_json"]["control_plane_run_record"]["run_id"]
    finally:
        await pipeline.close()
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("DROP TRIGGER stop_publication")
        await conn.commit()
    restarted = await publication_pipeline(test_root, workspace, db_path)

    async def forbidden_redispatch(**_kwargs):
        raise AssertionError("accepted work must not be dispatched during publication recovery")

    restarted.orchestrator.execute_epic = forbidden_redispatch
    try:
        result = await restarted.run_epic("publication_epic", build_id="build", session_id="publication-session")
        assert result.succeeded and result.observation == "published" and result.transcript == ()
        assert result.run_id == cp_run_id
        assert await restarted.async_cards.read_completion_receipt("ISSUE-1") == receipt
        current = await restarted.run_ledger.get_run("publication-session")
        assert current["status"] == "done"
        assert current["artifact_json"]["control_plane_run_record"]["run_id"] == cp_run_id
        assert (await restarted.sessions.get_session("publication-session"))["status"] == "done"
        snapshot = await restarted.snapshots.get("publication-session")
        assert json.loads(snapshot["config_json"])["build_id"] == "build"
        async with aiosqlite.connect(db_path) as conn:
            assert await (await conn.execute("SELECT COUNT(*) FROM success_ledger")).fetchone() == (1,)
        # Matching concurrent reentry returns retained history without another effect.
        before = await asyncio.to_thread(Path(db_path).read_bytes)
        await asyncio.gather(*[restarted.run_epic("publication_epic", build_id="build", session_id="publication-session")
                              for _ in range(2)])
        assert await asyncio.to_thread(Path(db_path).read_bytes) == before
    finally:
        await restarted.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["request", "acceptance", "digest", "schema", "missing_plan", "lost_success",
                                  "sessions", "session_snapshots", "success_ledger", "run_ledger", "build", "epic"])
# Layer: integration
async def test_reentry_rejects_conflict_or_lost_evidence_without_resealing(test_root, workspace, db_path, damage):
    pipeline = await publication_pipeline(test_root, workspace, db_path)

    async def execute_fixture(**_kwargs):
        await accept_publication_card(pipeline, workspace)

    pipeline.orchestrator.execute_epic = execute_fixture
    try:
        await pipeline.run_epic("publication_epic", build_id="build", session_id="publication-session")
    finally:
        await pipeline.close()
    restarted = await publication_pipeline(test_root, workspace, db_path)
    journal = restarted.epic_publication.repository.db_path
    try:
        if damage == "acceptance":
            await restarted.async_cards.reset_build("build")
        elif damage == "epic":
            path = test_root / "model/core/epics/publication_epic.json"
            payload = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
            payload["issues"][0]["summary"] = "A different workload request"
            await asyncio.to_thread(path.write_text, json.dumps(payload), encoding="utf-8")
        elif damage in {"lost_success", "sessions", "session_snapshots", "success_ledger", "run_ledger"}:
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute("DELETE FROM success_ledger" if damage == "lost_success" else f"DROP TABLE {damage}")
                await conn.commit()
        elif damage in {"digest", "schema", "missing_plan"}:
            async with aiosqlite.connect(journal) as conn:
                sql = {"digest": "UPDATE epic_publications SET digest = 'broken'",
                       "schema": "UPDATE epic_publications SET payload = json_set(payload, '$.plan.schema_version', 'unknown')",
                       "missing_plan": "DELETE FROM epic_publications"}[damage]
                await conn.execute(sql)
                await conn.commit()
        before = await asyncio.to_thread(Path(db_path).read_bytes)
        before_journal = await asyncio.to_thread(journal.read_bytes)
        request = dict(build_id="other-build" if damage == "build" else "build", session_id="publication-session",
                       model_override="changed-request" if damage == "request" else "")
        if damage in {"request", "build", "epic"}:
            with pytest.raises(ValueError):
                await restarted.run_epic("publication_epic", **request)
        else:
            result = await restarted.run_epic("publication_epic", **request)
            assert result.observation == "unresolved" and not result.succeeded
            assert result.reason
        assert await asyncio.to_thread(Path(db_path).read_bytes) == before
        assert await asyncio.to_thread(journal.read_bytes) == before_journal
    finally:
        await restarted.close()


@pytest.mark.asyncio
# Layer: integration
async def test_failed_workload_restart_returns_verified_failure_without_redispatch(test_root, workspace, db_path):
    pipeline = await publication_pipeline(test_root, workspace, db_path)

    async def failed_workload(**_kwargs):
        await abort_publication(pipeline, db_path, "session")
        raise ExecutionFailed("retained workload failure")

    pipeline.orchestrator.execute_epic = failed_workload
    try:
        result = await pipeline.run_epic("publication_epic", build_id="build", session_id="publication-session")
        assert result.observation == "unresolved" and not result.succeeded
        assert "restart-publication-fault" in result.reason and result.evidence_refs
    finally:
        await pipeline.close()
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("DROP TRIGGER stop_publication")
        await conn.commit()
    restarted = await publication_pipeline(test_root, workspace, db_path)

    async def forbidden_redispatch(**_kwargs):
        raise AssertionError("failed workload was redispatched")

    restarted.orchestrator.execute_epic = forbidden_redispatch
    try:
        result = await restarted.run_epic("publication_epic", build_id="build", session_id="publication-session")
        assert result.observation == "published" and result.result_class.value == "failed"
        assert not result.succeeded and result.reason == "retained workload failure"
        assert (await restarted.sessions.get_session("publication-session"))["status"] == "failed"
        assert await restarted.success.get("publication-session") is None
    finally:
        await restarted.close()
