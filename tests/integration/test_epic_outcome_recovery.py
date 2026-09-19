"""Retain workload termination before finalization reads and preparation writes."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite
import pytest

from orket.core.domain.execution import ExecutionTurn
from orket.exceptions import ExecutionFailed
from orket.runtime.execution.epic_run_finalize import EpicRunFinalizer
from tests.integration.test_epic_closeout_process import read_barrier
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline
from tests.integration.test_epic_publication_recovery_process import launch, retained_rows

pytestmark = pytest.mark.integration


async def forbid_dispatch(**_kwargs):
    raise AssertionError("Retained work was dispatched again")


async def damage_outcome(journal, db_path, damage):
    statements = {
        "digest": "UPDATE epic_workload_outcomes SET digest = 'broken'",
        "schema": "UPDATE epic_workload_outcomes SET payload = json_set(payload, '$.schema_version', 'unknown')",
        "missing": "DELETE FROM epic_workload_outcomes",
        "run_missing": "DELETE FROM run_ledger",
        "run_conflict": "UPDATE run_ledger SET artifact_json = json_set(artifact_json, '$.control_plane_run_record.run_id', 'wrong-run')",
    }
    if damage in statements:
        async with aiosqlite.connect(db_path if damage.startswith("run_") else journal) as conn:
            await conn.execute(statements[damage])
            await conn.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", [None, "digest", "schema", "missing", "request", "run_missing", "run_conflict"])
# Layer: integration
async def test_restart_recovers_after_outcome_inspection_failure(test_root, workspace, db_path, monkeypatch, damage):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    obstruction = workspace / "source-inspection-obstruction"
    await asyncio.to_thread(obstruction.mkdir)

    async def failed_inspection(*_args, **_kwargs):
        return await asyncio.to_thread(obstruction.read_text, encoding="utf-8")

    async def execute_fixture(**kwargs):
        await accept_publication_card(pipeline, workspace)
        kwargs["epic"].params["retained_runtime_note"] = "captured after setup"
        pipeline.orchestrator.transcript.append(ExecutionTurn(timestamp=None, role="coder", issue_id="ISSUE-1", content="retained output"))

    pipeline.orchestrator.execute_epic = execute_fixture
    try:
        with monkeypatch.context() as patch:
            patch.setattr(EpicRunFinalizer, "_resolve_source_attribution_failure", failed_inspection)
            observed = await pipeline.run_epic("publication_epic", build_id="build", session_id="publication-session")
            assert observed.observation == "unresolved" and not observed.succeeded
        receipt = await pipeline.async_cards.read_completion_receipt("ISSUE-1")
        before = await pipeline.run_ledger.get_run("publication-session")
    finally:
        await pipeline.close()
    restarted = await publication_pipeline(test_root, workspace, db_path)
    restarted.orchestrator.execute_epic = forbid_dispatch
    try:
        if damage:
            journal = restarted.epic_publication.repository.db_path
            await damage_outcome(journal, db_path, damage)
            database_bytes = await asyncio.to_thread(Path(db_path).read_bytes)
            journal_bytes = await asyncio.to_thread(journal.read_bytes)
            if damage == "request":
                with pytest.raises(ValueError):
                    await restarted.run_epic("publication_epic", build_id="other", session_id="publication-session")
            else:
                observed = await restarted.run_epic("publication_epic", build_id="build", session_id="publication-session")
                assert observed.observation == "unresolved" and not observed.succeeded
            assert await asyncio.to_thread(Path(db_path).read_bytes) == database_bytes
            assert await asyncio.to_thread(journal.read_bytes) == journal_bytes
            return
        result = await restarted.run_epic("publication_epic", build_id="build", session_id="publication-session")
        assert result.succeeded
        assert list(result.transcript) == [{"step_index": 0, "role": "coder", "issue": "ISSUE-1", "summary": "retained output", "note": ""}]
        snapshot = await restarted.snapshots.get("publication-session")
        assert json.loads(snapshot["config_json"])["epic"]["params"]["retained_runtime_note"] == "captured after setup"
        assert await restarted.async_cards.read_completion_receipt("ISSUE-1") == receipt
        after = await restarted.run_ledger.get_run("publication-session")
        assert after["status"] == "done"
        assert after["artifact_json"]["control_plane_run_record"]["run_id"] == before["artifact_json"]["control_plane_run_record"]["run_id"]
    finally:
        await restarted.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["workload_unknown", "outcome_failed"])
# Layer: integration
async def test_native_restart_preserves_unknown_or_failed_workload(test_root, workspace, db_path, stage):
    child = await launch(test_root, workspace, db_path, "kill", stage)
    resumed = []
    try:
        await asyncio.wait_for(read_barrier(child), timeout=40)
        child.kill()
        await asyncio.wait_for(child.communicate(), timeout=10)
        before = await retained_rows(db_path)
        resumed = [await launch(test_root, workspace, db_path, "resume", stage) for _ in range(2)]
        replies = await asyncio.wait_for(asyncio.gather(*(p.communicate() for p in resumed)), timeout=50)
        expected = "E_EPIC_WORKLOAD_OUTCOME_UNCERTAIN" if stage == "workload_unknown" else "retained native workload failure"
        for process, (_stdout, stderr) in zip(resumed, replies, strict=True):
            assert process.returncode != 0
            assert expected in stderr.decode(errors="replace")
        after = await retained_rows(db_path)
        if stage == "workload_unknown":
            assert after == before
        else:
            assert after["run_ledger"][0]["status"] == "failed"
            assert after["sessions"][0]["status"] == "failed"
        assert after.get("success_ledger", []) == []
    finally:
        for process in [child, *resumed]:
            if process.returncode is None:
                process.kill()
            await process.communicate()


@pytest.mark.asyncio
# Layer: integration
async def test_started_workload_without_retained_outcome_refuses_redispatch(test_root, workspace, db_path):
    pipeline = await publication_pipeline(test_root, workspace, db_path)

    async def interrupted_workload(**_kwargs):
        await accept_publication_card(pipeline, workspace)
        raise asyncio.CancelledError

    pipeline.orchestrator.execute_epic = interrupted_workload
    try:
        with pytest.raises(asyncio.CancelledError):
            await pipeline.run_epic("publication_epic", build_id="build", session_id="publication-session")
        receipt = await pipeline.async_cards.read_completion_receipt("ISSUE-1")
    finally:
        await pipeline.close()
    restarted = await publication_pipeline(test_root, workspace, db_path)
    restarted.orchestrator.execute_epic = forbid_dispatch
    try:
        observed = await restarted.run_epic("publication_epic", build_id="build", session_id="publication-session")
        assert observed.observation == "unresolved" and not observed.succeeded
        assert "E_EPIC_WORKLOAD_OUTCOME_UNCERTAIN" in observed.reason
        assert await restarted.async_cards.read_completion_receipt("ISSUE-1") == receipt
        assert (await restarted.run_ledger.get_run("publication-session"))["status"] == "running"
        assert await restarted.success.get("publication-session") is None
    finally:
        await restarted.close()


@pytest.mark.asyncio
# Layer: integration
async def test_retained_workload_failure_survives_initial_preparation_write_abort(test_root, workspace, db_path):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    journal = pipeline.epic_publication.repository.db_path

    async def failed_workload(**_kwargs):
        async with aiosqlite.connect(journal) as conn:
            await conn.execute("CREATE TRIGGER stop_preparation BEFORE INSERT ON epic_preparations "
                               "BEGIN SELECT RAISE(ABORT, 'preparation-retention-fault'); END")
            await conn.commit()
        raise ExecutionFailed("original workload failure")

    pipeline.orchestrator.execute_epic = failed_workload
    try:
        observed = await pipeline.run_epic("publication_epic", build_id="build", session_id="publication-session")
        assert observed.observation == "unresolved" and not observed.succeeded
        assert "preparation-retention-fault" in observed.reason
    finally:
        await pipeline.close()
    async with aiosqlite.connect(journal) as conn:
        await conn.execute("DROP TRIGGER stop_preparation")
        await conn.commit()
    restarted = await publication_pipeline(test_root, workspace, db_path)
    restarted.orchestrator.execute_epic = forbid_dispatch
    try:
        observed = await restarted.run_epic("publication_epic", build_id="build", session_id="publication-session")
        assert observed.observation == "published" and not observed.succeeded
        assert "original workload failure" in observed.reason
        row = await restarted.run_ledger.get_run("publication-session")
        assert row["status"] == "failed"
        assert row["failure_class"] == "ExecutionFailed"
        assert await restarted.success.get("publication-session") is None
    finally:
        await restarted.close()
