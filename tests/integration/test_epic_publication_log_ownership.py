"""Required completion logs remain owned after their independently observed store effects."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from types import SimpleNamespace

import aiosqlite
import pytest

from orket.adapters.observability import log_publication
from orket.application.services.runtime_execution_result_service import RuntimeExecutionCancelled
from orket.core.contracts.runtime_execution_result import RuntimeExecutionResult
from tests.helpers.runtime_verification_hold import settle, sqlite_response
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
EVENT_PHASES = {"session_end": 1, "success_recorded": 3, "orchestrator_epic_complete": 3}
SESSION_ID = "publication-session"


def hold_publication(monkeypatch, event, failure):
    hold = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                           expired=False, thread=None)
    original = log_publication._append_line_sync

    def append(path, line):
        if json.loads(line).get("event") != event or hold.entered.is_set():
            return original(path, line)
        hold.thread = threading.get_ident()
        hold.entered.set()
        try:
            hold.expired = not hold.release.wait(10)
            assert not hold.expired, "required completion publication was not released"
            original(path, line)
            if failure is not None:
                raise failure
        finally:
            hold.finished.set()

    monkeypatch.setattr(log_publication, "_append_line_sync", append)
    return hold


async def publication_phase(journal):
    async with aiosqlite.connect(journal) as connection:
        row = await (await connection.execute(
            "SELECT payload FROM epic_publications WHERE session_id = ?", (SESSION_ID,))).fetchone()
    return json.loads(row[0])["phase"]


async def assert_retained_effects(pipeline, event):
    assert (await pipeline.sessions.get_session(SESSION_ID))["status"] == "done"
    assert (await pipeline.run_ledger.get_run(SESSION_ID))["status"] == "done"
    assert await pipeline.async_cards.read_completion_receipt("ISSUE-1") is not None
    assert await publication_phase(pipeline.epic_publication.repository.db_path) == EVENT_PHASES[event]
    if event != "session_end":
        assert (await pipeline.success.get(SESSION_ID))["success_type"] == "EPIC_COMPLETED"
        assert await pipeline.snapshots.get(SESSION_ID) is not None


async def interrupt_publication(task, stop):
    if stop == "cancel":
        task.cancel("first completion publication interruption")
        await asyncio.sleep(0)
        task.cancel("repeated completion publication interruption")
    if stop == "timeout":
        return asyncio.create_task(asyncio.wait_for(task, 0.02))
    return task


async def capture_publication(pipeline, cancellations):
    try:
        return await pipeline.run_epic("publication_epic", build_id="build", session_id=SESSION_ID)
    except RuntimeExecutionCancelled as failure:
        cancellations.append(failure)
        raise


async def assert_cancelled_observation(pipeline, failure):
    result = failure.result
    assert isinstance(result, RuntimeExecutionResult)
    assert result.observation == "cancelled" and not result.succeeded
    assert result.session_id == SESSION_ID and result.build_id == "build" and result.publication_ref is None
    assert result.run is not None and result.final_truth is not None
    control_plane = pipeline.epic_publication.control_plane
    assert result.run == await control_plane.execution_repository.get_run_record(run_id=result.run_id)
    assert result.final_truth == await control_plane.publication.repository.get_final_truth(run_id=result.run_id)
    async with pipeline.epic_publication.repository.transaction(SESSION_ID) as transaction:
        admission, publication = await transaction.get_admission(), await transaction.get()
    assert f"epic-admission:{SESSION_ID}:sha256:{admission.digest()}" in result.evidence_refs
    assert f"epic-publication:{SESSION_ID}:sha256:{publication.digest()}" in result.evidence_refs


async def assert_outcome(waiter, cancellations, record_property, *, stop, fails):
    if fails:
        result = await waiter
        assert result.observation == "unresolved" and not result.succeeded
        assert "OSError: required completion append acknowledgement failed" in result.reason
        assert not cancellations
        return None
    if stop == "none":
        assert (await waiter).succeeded
        assert not cancellations
        return None
    try:
        await waiter
    except TimeoutError as outer:
        # CPython 3.11 wait_for wraps this exact public cancellation as its cause.
        assert stop == "timeout" and type(outer) is TimeoutError
        failure = outer.__cause__
        assert outer.__context__ is failure
        envelope = "TimeoutError.__cause__"
    except RuntimeExecutionCancelled as outer:
        # CPython 3.12's timeout context passes a CancelledError subclass through.
        failure = outer
        envelope = "direct RuntimeExecutionCancelled"
    else:
        pytest.fail("Interrupted publication returned without its typed cancellation")
    assert len(cancellations) == 1 and failure is cancellations[0]
    assert type(failure) is RuntimeExecutionCancelled
    cause = failure.__cause__
    assert type(cause) is asyncio.CancelledError and failure.__context__ is cause
    assert cause.args == (("first completion publication interruption",) if stop == "cancel" else ())
    record_property("cancellation_envelope", envelope)
    record_property("runtime_cancellation_result", failure.result.model_dump_json())
    return failure


@pytest.mark.parametrize("event", EVENT_PHASES)
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("fails", [False, True])
async def test_completion_publication_retains_native_attempt_and_recovery(
    test_root, workspace, db_path, monkeypatch, record_property, event, stop, fails,
):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    dispatches = []

    async def execute_fixture(**_kwargs):
        dispatches.append(SESSION_ID)
        await accept_publication_card(pipeline, workspace)

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", execute_fixture)
    failure = OSError("required completion append acknowledgement failed") if fails else None
    hold = hold_publication(monkeypatch, event, failure)
    cancellations = []
    task = asyncio.create_task(capture_publication(pipeline, cancellations))
    waiter = task
    try:
        assert await asyncio.to_thread(hold.entered.wait, 8), "completion publication did not begin"
        await assert_retained_effects(pipeline, event)
        interruption_started = time.perf_counter()
        waiter = await interrupt_publication(task, stop)
        assert await sqlite_response(test_root / "responsiveness.sqlite3", record_property) < 0.5
        done, _ = await asyncio.wait({waiter}, timeout=0.1)
        assert not done and not task.done(), "completion returned before its native log attempt settled"
        assert task.cancelling() == {"none": 0, "cancel": 2, "timeout": 1}[stop]
        if stop == "timeout":
            assert time.perf_counter() - interruption_started >= 0.02
        hold.release.set()
        cancelled = await assert_outcome(waiter, cancellations, record_property, stop=stop, fails=fails)
        if cancelled is not None:
            await assert_cancelled_observation(pipeline, cancelled)
        assert hold.finished.is_set() and not hold.expired and hold.thread != threading.get_ident()
        rows = (await asyncio.to_thread((workspace / "orket.log").read_text, encoding="utf-8")).splitlines()
        assert any(json.loads(row).get("event") == event for row in rows)
        if fails or stop != "none":
            await assert_retained_effects(pipeline, event)
        recovered = await pipeline.run_epic("publication_epic", build_id="build", session_id=SESSION_ID)
        assert recovered.succeeded and dispatches == [SESSION_ID]
        assert await publication_phase(pipeline.epic_publication.repository.db_path) == 4
        record_property("required_publication", json.dumps({"event": event, "stop": stop, "failure": fails,
            "native_settled": hold.finished.is_set(), "dispatch_count": len(dispatches), "recovered_phase": 4}))
    finally:
        try:
            await settle(task, hold)
        finally:
            try:
                await asyncio.gather(waiter, return_exceptions=True)
            finally:
                await pipeline.close()
