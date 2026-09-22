"""Layer: integration. Real Kernel workers and SQLite publication survive interruption."""

import asyncio
import threading

import aiosqlite
import pytest

from orket.core.domain import AttemptState
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime
from tests.helpers.kernel_runtime import engine_events
from tests.helpers.kernel_state_probe import hold_native, interrupt_owned, kernel_app, responsive_sqlite
from tests.integration.test_kernel_publication_input_capture import hold_first_lookup

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("credential_runtime")]


def action_request():
    return {
        "contract_version": "kernel_api/v1",
        "session_id": "owned-session",
        "trace_id": "owned-trace",
        "proposal": {"proposal_type": "action.tool_call", "payload": {"tool_name": "local.echo"}},
    }


async def test_native_admission_retains_environment_and_responsive_sqlite(tmp_path, monkeypatch, record_property):
    app = kernel_app(tmp_path)
    async with app.router.lifespan_context(app):
        engine = app.state.api_runtime_context.engine
        hold = hold_native(monkeypatch, engine.kernel_gateway_facade, "admit_proposal")
        task = asyncio.create_task(engine.kernel_admit_proposal_async(action_request()))
        try:
            assert await asyncio.wait_for(asyncio.to_thread(hold.entered.wait, 10), 10)
            monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "false")
            await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
            assert hold.worker != threading.get_ident() and not hold.expired
            hold.release.set()
            result = await asyncio.wait_for(task, 10)
            assert result["admission_decision"]["decision"] == "ACCEPT_TO_UNIFY"
            assert result["control_plane_run_id"] == "kernel-action-run:owned-session:owned-trace"
            with pytest.raises(ValueError, match="disabled"):
                await engine.kernel_admit_proposal_async({**action_request(), "session_id": "next-session"})
        finally:
            hold.release.set()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("operation", ["admit_proposal", "commit_proposal", "end_session"])
@pytest.mark.parametrize("timed", [False, True], ids=["repeated-cancel", "timeout"])
async def test_engine_interruption_waits_for_real_publication(tmp_path, monkeypatch, operation, timed):
    app = kernel_app(tmp_path)
    async with app.router.lifespan_context(app):
        engine, request = app.state.api_runtime_context.engine, action_request()
        if operation != "admit_proposal":
            admitted = await engine.kernel_admit_proposal_async(request)
            request.update(
                proposal_digest=admitted["proposal_digest"],
                admission_decision_digest=admitted["decision_digest"],
                execution_result_digest="a" * 64,
            )
        entered, release = hold_first_lookup(monkeypatch, engine.control_plane_execution_repository)
        task = asyncio.create_task(getattr(engine, "kernel_" + operation + "_async")(request))
        waiter = task
        try:
            await asyncio.wait_for(entered.wait(), 10)
            waiter = await interrupt_owned(task, release, timed=timed)
            with pytest.raises(TimeoutError if timed else asyncio.CancelledError):
                await asyncio.wait_for(waiter, 10)
            run = await engine.control_plane_execution_repository.get_run_record(
                run_id="kernel-action-run:owned-session:owned-trace"
            )
            assert run is not None
            attempt = await engine.control_plane_execution_repository.get_attempt_record(
                attempt_id="kernel-action-attempt:owned-session:owned-trace:0001"
            )
            expected = {
                "admit_proposal": AttemptState.CREATED,
                "commit_proposal": AttemptState.COMPLETED,
                "end_session": AttemptState.ABANDONED,
            }
            assert attempt.attempt_state == expected[operation]
            event = {
                "admit_proposal": "admission.decided",
                "commit_proposal": "commit.recorded",
                "end_session": "session.ended",
            }[operation]
            assert len([row for row in await engine_events(engine, "owned-session") if row["event_type"] == event]) == 1
        finally:
            release.set()
            await asyncio.gather(task, waiter, return_exceptions=True)


async def test_publication_failure_is_visible_after_cancel(tmp_path, monkeypatch):
    app = kernel_app(tmp_path)
    async with app.router.lifespan_context(app):
        engine = app.state.api_runtime_context.engine
        entered, release = asyncio.Event(), asyncio.Event()

        async def fail_lookup(*, run_id):
            entered.set()
            await release.wait()
            async with aiosqlite.connect(tmp_path / "failure.sqlite3") as connection:
                await connection.execute("SELECT * FROM absent_publication_table")

        monkeypatch.setattr(engine.control_plane_execution_repository, "get_run_record", fail_lookup)
        task = asyncio.create_task(engine.kernel_admit_proposal_async(action_request()))
        try:
            await asyncio.wait_for(entered.wait(), 10)
            await interrupt_owned(task, release, timed=False)
            with pytest.raises(aiosqlite.OperationalError, match="absent_publication_table"):
                await asyncio.wait_for(task, 10)
            assert any(row["event_type"] == "admission.decided" for row in await engine_events(engine, "owned-session"))
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
