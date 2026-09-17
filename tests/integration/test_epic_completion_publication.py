"""Real SQLite aborts cannot publish success ahead of failed finalization writes."""
from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.application.services.cards_epic_control_plane_service import CardsEpicControlPlaneError
from orket.core.domain import AttemptState, RunState
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets
from tests.helpers.card_completion import complete_existing_card

pytestmark = pytest.mark.integration


async def publication_pipeline(root, workspace, db_path):
    await asyncio.to_thread(_write_epic_assets, root, "publication_epic")
    return await asyncio.to_thread(ExecutionPipeline, workspace, department="core", db_path=db_path, config_root=root)


async def accept_publication_card(pipeline, workspace):
    service = pipeline.runtime_context.card_completion
    await complete_existing_card(pipeline.async_cards, "ISSUE-1", workspace, service=service)


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["control_plane", "run_ledger"])
# Layer: integration
async def test_finalization_abort_does_not_leave_premature_session_or_success(test_root, workspace, db_path, monkeypatch, boundary):
    pipeline = await publication_pipeline(test_root, workspace, db_path)

    async def execute_fixture(**_kwargs):
        await accept_publication_card(pipeline, workspace)
        target = pipeline.orchestrator.control_plane_execution_repository.db_path if boundary == "control_plane" else db_path
        table = "control_plane_runs" if boundary == "control_plane" else "run_ledger"
        condition = "json_extract(NEW.payload_json, '$.lifecycle_state') = 'completed'" if boundary == "control_plane" else "NEW.status = 'done'"
        async with aiosqlite.connect(target) as conn:
            await conn.execute(f"CREATE TRIGGER abort_completion BEFORE UPDATE ON {table} WHEN {condition} "
                               "BEGIN SELECT RAISE(ABORT, 'publication-fault'); END")
            await conn.commit()

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", execute_fixture)
    try:
        observed = await pipeline.run_epic('publication_epic', build_id='build', session_id='publication-session')
        assert observed.observation == "unresolved" and not observed.succeeded
        assert re.search('publication-fault', observed.reason or "")
        session = await pipeline.sessions.get_session("publication-session")
        ledger = await pipeline.run_ledger.get_run("publication-session")
        assert session["status"] != "done"
        assert ledger["status"] != "done"
        async with aiosqlite.connect(db_path) as conn:
            exists = await (await conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'success_ledger'")).fetchone()
            if exists:
                assert await (await conn.execute("SELECT COUNT(*) FROM success_ledger")).fetchone() == (0,)
        if boundary == "control_plane":
            cp = pipeline.orchestrator.control_plane_execution_repository
            records = ledger["artifact_json"]["control_plane_run_record"]
            run = await cp.get_run_record(run_id=records["run_id"])
            attempt = await cp.get_attempt_record(attempt_id=run.current_attempt_id)
            assert run.lifecycle_state == RunState.EXECUTING
            assert attempt.attempt_state == AttemptState.EXECUTING
            assert await pipeline.orchestrator.control_plane_repository.get_final_truth(run_id=run.run_id) is None
            assert await cp.get_step_record(step_id=pipeline.cards_epic_control_plane.closeout_step_id_for(run_id=run.run_id)) is None
    finally:
        await pipeline.close()


@pytest.mark.asyncio
# Layer: integration
async def test_publication_error_does_not_reclassify_accepted_work(test_root, workspace, db_path, monkeypatch):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    obstruction = workspace / "publication-obstruction"
    await asyncio.to_thread(obstruction.mkdir)

    async def execute_fixture(**_kwargs):
        await accept_publication_card(pipeline, workspace)

    async def failed_materialization(**_kwargs):
        await asyncio.to_thread(obstruction.write_text, "cannot replace a directory", encoding="utf-8")

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", execute_fixture)
    monkeypatch.setattr(pipeline, "_materialize_run_summary", failed_materialization)
    try:
        observed = await pipeline.run_epic('publication_epic', build_id='build', session_id='publication-session')
        assert observed.observation == "unresolved" and not observed.succeeded
        assert re.search('materialize run summary', observed.reason or "")
        ledger = await pipeline.run_ledger.get_run("publication-session")
        run_id = ledger["artifact_json"]["control_plane_run_record"]["run_id"]
        cp = pipeline.orchestrator.control_plane_execution_repository
        assert (await cp.get_run_record(run_id=run_id)).lifecycle_state == RunState.COMPLETED
        assert (await pipeline.orchestrator.control_plane_repository.get_final_truth(run_id=run_id)).result_class.value == "success"
        assert ledger["status"] != "done"
        assert (await pipeline.sessions.get_session("publication-session"))["status"] != "done"
    finally:
        await pipeline.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["missing_step", "journal_digest"])
# Layer: integration
async def test_closeout_reentry_preserves_evidence_and_rejects_conflicting_or_missing_history(test_root, workspace, db_path, monkeypatch, damage):
    pipeline = await publication_pipeline(test_root, workspace, db_path)

    async def execute_fixture(**_kwargs):
        await accept_publication_card(pipeline, workspace)

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", execute_fixture)
    try:
        await pipeline.run_epic("publication_epic", build_id="build", session_id="publication-session")
        ledger = await pipeline.run_ledger.get_run("publication-session")
        run_id = ledger["artifact_json"]["control_plane_run_record"]["run_id"]
        path = Path(pipeline.orchestrator.control_plane_execution_repository.db_path)
        before = hashlib.sha256(await asyncio.to_thread(path.read_bytes)).hexdigest()
        first, second = await asyncio.gather(*[
            pipeline.cards_epic_control_plane.finalize_execution(run_id=run_id, session_status="done") for _ in range(2)])
        assert first == second
        with pytest.raises(ValueError):
            await pipeline.cards_epic_control_plane.finalize_execution(run_id=run_id, session_status="failed")
        assert hashlib.sha256(await asyncio.to_thread(path.read_bytes)).hexdigest() == before
        async with aiosqlite.connect(path) as conn:
            if damage == "missing_step":
                await conn.execute("DELETE FROM control_plane_steps WHERE step_id = ?",
                                   (pipeline.cards_epic_control_plane.closeout_step_id_for(run_id=run_id),))
            else:
                await conn.execute("UPDATE effect_journal_entries SET payload_json = json_set(payload_json, '$.entry_digest', ?) "
                                   "WHERE run_id = ? AND publication_sequence = 2", ("0" * 64, run_id))
            await conn.commit()
        damaged = hashlib.sha256(await asyncio.to_thread(path.read_bytes)).hexdigest()
        error_type = CardsEpicControlPlaneError if damage == "missing_step" else ValueError
        with pytest.raises(error_type, match="CLOSEOUT_EVIDENCE_MISSING" if damage == "missing_step" else "digest"):
            await pipeline.cards_epic_control_plane.finalize_execution(run_id=run_id, session_status="done")
        assert hashlib.sha256(await asyncio.to_thread(path.read_bytes)).hexdigest() == damaged
    finally:
        await pipeline.close()


@pytest.mark.asyncio
# Layer: integration
async def test_cancellation_rolls_back_closeout_before_publishing_success(test_root, workspace, db_path, monkeypatch):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    writing, release = asyncio.Event(), asyncio.Event()
    save_attempt = AsyncControlPlaneExecutionRepository.save_attempt_record

    async def pause_after_attempt(repo, *, record):
        result = await save_attempt(repo, record=record)
        if record.attempt_state == AttemptState.COMPLETED:
            writing.set()
            await release.wait()
        return result

    async def execute_fixture(**_kwargs):
        await accept_publication_card(pipeline, workspace)

    monkeypatch.setattr(AsyncControlPlaneExecutionRepository, "save_attempt_record", pause_after_attempt)
    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", execute_fixture)
    task = asyncio.create_task(pipeline.run_epic("publication_epic", build_id="build", session_id="publication-session"))
    try:
        await asyncio.wait_for(writing.wait(), timeout=10)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        ledger = await pipeline.run_ledger.get_run("publication-session")
        run_id = ledger["artifact_json"]["control_plane_run_record"]["run_id"]
        cp = pipeline.orchestrator.control_plane_execution_repository
        run = await cp.get_run_record(run_id=run_id)
        assert run.lifecycle_state == RunState.EXECUTING
        assert (await cp.get_attempt_record(attempt_id=run.current_attempt_id)).attempt_state == AttemptState.EXECUTING
        assert await pipeline.orchestrator.control_plane_repository.get_final_truth(run_id=run_id) is None
        assert (await pipeline.sessions.get_session("publication-session"))["status"] != "done"
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await pipeline.close()
