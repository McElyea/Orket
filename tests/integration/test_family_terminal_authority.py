"""Composed family paths must not commit success before their terminal attempt."""

from __future__ import annotations

import asyncio
import json

import aiosqlite
import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.core.domain import AttemptState, RunState
from tests.helpers.governed_agent_clock import elapsed_agent_clock as elapsed_agent_clock
from tests.helpers.outward_authorization import approve, outward_api, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline
from tests.integration.test_governed_agent_acceptance_failures import _run as run_agent_fixture
from tests.runtime.governed_agent_test_support import TEMPLATE_ROOT, agent_request

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("elapsed_agent_clock")]
FAULT = "bt5-family-terminal-attempt-interrupted"


async def outward_flow(tmp_path, boundary):
    db, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        proposal = await submit_sequence(client, calls[:1])
        response = await approve(client, proposal)
        observed = {"status_code": response.status_code, "body": response.json()}
    assert context.closed and context.active_background_task_count == 0
    return db, observed


async def card_flow(test_root, workspace, db_path, monkeypatch):
    pipeline = await publication_pipeline(test_root, workspace, db_path)

    async def accepted_work(**_kwargs):
        await accept_publication_card(pipeline, workspace)

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", accepted_work)
    try:
        observed = await pipeline.run_card("publication_epic", build_id="build", session_id="family-publication")
        db = pipeline.orchestrator.control_plane_execution_repository.db_path
        return db, {"succeeded": observed.succeeded, "observation": observed.observation, "reason": observed.reason}
    finally:
        await pipeline.close()


async def agent_flow(tmp_path):
    source = await asyncio.to_thread((TEMPLATE_ROOT / "governed_agent.py").read_text, encoding="utf-8")
    try:
        execution, _ = await run_agent_fixture(tmp_path, source, agent_request())
        observed = {"lifecycle": execution.run.lifecycle_state.value,
                    "truth": execution.final_truth.model_dump(mode="json") if execution.final_truth else None}
    except RuntimeError as exc:
        assert str(exc) == FAULT
        observed = {"error": str(exc)}
    return tmp_path / "agent.sqlite3", observed


async def retained_results(db):
    async with aiosqlite.connect(db) as connection:
        cursor = await connection.execute("SELECT payload_json FROM control_plane_runs ORDER BY run_id")
        runs = [json.loads(row[0]) for row in await cursor.fetchall()]
    assert runs, "The composed flow must have admitted a real run."
    repository = AsyncControlPlaneRecordRepository(db)
    results = []
    for run in runs:
        truth = await repository.get_final_truth(run_id=run["run_id"])
        results.append({"run": run, "truth": truth.model_dump(mode="json") if truth else None})
    return results


@pytest.mark.parametrize("family", ["outward", "cards", "governed_agent"])
@pytest.mark.parametrize("interrupt", [None, "attempt", "run"], ids=["complete", "attempt-write-interrupted", "run-write-interrupted"])
# Layer: integration
async def test_family_terminal_success_requires_completed_attempt(
    family, interrupt, tmp_path, test_root, workspace, db_path, boundary, monkeypatch,
):
    original = AsyncControlPlaneExecutionRepository.save_attempt_record
    original_run = AsyncControlPlaneExecutionRepository.save_run_record
    interrupted = []

    async def save_attempt(repository, *, record):
        if interrupt == "attempt" and record.attempt_state is AttemptState.COMPLETED:
            interrupted.append(record.run_id)
            raise RuntimeError(FAULT)
        return await original(repository, record=record)

    async def save_run(repository, *, record):
        if interrupt == "run" and record.lifecycle_state is RunState.COMPLETED:
            interrupted.append(record.run_id)
            raise RuntimeError(FAULT)
        return await original_run(repository, record=record)

    monkeypatch.setattr(AsyncControlPlaneExecutionRepository, "save_attempt_record", save_attempt)
    monkeypatch.setattr(AsyncControlPlaneExecutionRepository, "save_run_record", save_run)
    if family == "outward":
        db, observed = await outward_flow(tmp_path, boundary)
    elif family == "cards":
        db, observed = await card_flow(test_root, workspace, db_path, monkeypatch)
    else:
        db, observed = await agent_flow(tmp_path)
    retained = await retained_results(db)
    successes = [row for row in retained if row["truth"] and row["truth"]["result_class"] == "success"]
    if interrupt:
        assert interrupted, (family, observed, retained)
        assert not successes, (family, observed, successes)
    else:
        assert not interrupted and successes, (family, observed, retained)
        execution = AsyncControlPlaneExecutionRepository(db)
        for row in successes:
            attempt = await execution.get_attempt_record(attempt_id=row["run"]["current_attempt_id"])
            assert row["run"]["lifecycle_state"] == "completed"
            assert attempt.attempt_state is AttemptState.COMPLETED and attempt.end_timestamp is not None
