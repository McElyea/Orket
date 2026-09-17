"""Retained preparation covers failures before a publication plan is ready."""
from __future__ import annotations

import asyncio
import re

import aiosqlite
import pytest

from tests.helpers.epic_publication_recovery_worker import configure_local_export_probe
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["closeout", "receipts", "summary", "summary_write"])
# Layer: integration
async def test_restart_recovers_preparation_without_reset_or_dispatch(test_root, workspace, db_path, stage):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    obstruction = workspace / "preparation-obstruction"
    await asyncio.to_thread(obstruction.mkdir)
    cp_db = pipeline.orchestrator.control_plane_execution_repository.db_path

    async def execute_fixture(**_kwargs):
        await accept_publication_card(pipeline, workspace)
        if stage == "summary_write":
            await asyncio.to_thread((workspace / "runs/publication-session/run_summary.json").mkdir,
                                    parents=True, exist_ok=True)
        if stage == "closeout":
            async with aiosqlite.connect(cp_db) as conn:
                await conn.execute("CREATE TRIGGER abort_preparation BEFORE UPDATE ON control_plane_runs "
                                   "WHEN json_extract(NEW.payload_json, '$.lifecycle_state') = 'completed' "
                                   "BEGIN SELECT RAISE(ABORT, 'preparation-abort'); END")
                await conn.commit()

    async def obstructed(**_kwargs):
        await asyncio.to_thread(obstruction.write_text, "cannot replace a directory", encoding="utf-8")

    pipeline.orchestrator.execute_epic = execute_fixture
    if stage in {"receipts", "summary"}:
        setattr(pipeline, "_materialize_protocol_receipts" if stage == "receipts" else "_materialize_run_summary", obstructed)
    try:
        observed = await pipeline.run_epic('publication_epic', build_id='build', session_id='publication-session')
        assert observed.observation == "unresolved" and not observed.succeeded
        receipt = await pipeline.async_cards.read_completion_receipt("ISSUE-1")
        ledger = await pipeline.run_ledger.get_run("publication-session")
        run_id = ledger["artifact_json"]["control_plane_run_record"]["run_id"]
    finally:
        await pipeline.close()
    if stage == "closeout":
        async with aiosqlite.connect(cp_db) as conn:
            await conn.execute("DROP TRIGGER abort_preparation")
            await conn.commit()
    if stage == "summary_write":
        await asyncio.to_thread((workspace / "runs/publication-session/run_summary.json").rmdir)
    restarted = await publication_pipeline(test_root, workspace, db_path)

    async def forbidden(**_kwargs):
        raise AssertionError("Preparation recovery redispatched accepted work")

    restarted.orchestrator.execute_epic = forbidden
    try:
        await restarted.run_epic("publication_epic", build_id="build", session_id="publication-session")
        assert await restarted.async_cards.read_completion_receipt("ISSUE-1") == receipt
        final = await restarted.run_ledger.get_run("publication-session")
        assert final["status"] == "done"
        assert final["artifact_json"]["control_plane_run_record"]["run_id"] == run_id
        assert (await restarted.success.get("publication-session"))["success_type"] == "EPIC_COMPLETED"
    finally:
        await restarted.close()


@pytest.mark.asyncio
# Layer: integration
async def test_enabled_export_error_retains_uncertainty_and_original_failure(test_root, workspace, db_path, monkeypatch):
    monkeypatch.setenv("ORKET_GITEA_ARTIFACT_EXPORT", "1")
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    configure_local_export_probe(pipeline.artifact_exporter)
    marker = workspace / "export-effect.txt"

    async def execute_fixture(**_kwargs):
        await accept_publication_card(pipeline, workspace)

    async def lost_reply(**_kwargs):
        await asyncio.to_thread(marker.write_text, "effect occurred", encoding="utf-8")
        raise OSError("export reply lost")

    pipeline.orchestrator.execute_epic = execute_fixture
    pipeline.artifact_exporter.export_run = lost_reply
    try:
        observed = await pipeline.run_epic('publication_epic', build_id='build', session_id='publication-session')
        assert observed.observation == "unresolved" and not observed.succeeded
        assert re.search('export reply lost', observed.reason or "")
    finally:
        await pipeline.close()
    restarted = await publication_pipeline(test_root, workspace, db_path)
    configure_local_export_probe(restarted.artifact_exporter)
    try:
        observed = await restarted.run_epic('publication_epic', build_id='build', session_id='publication-session')
        assert observed.observation == "unresolved" and not observed.succeeded
        assert re.search('E_EPIC_EXPORT_OUTCOME_UNCERTAIN', observed.reason or "")
        assert await asyncio.to_thread(marker.read_text, encoding="utf-8") == "effect occurred"
        assert (await restarted.run_ledger.get_run("publication-session"))["status"] == "running"
        assert await restarted.success.get("publication-session") is None
    finally:
        await restarted.close()
