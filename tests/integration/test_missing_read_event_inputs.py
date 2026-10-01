"""Integration: the missing-read publication boundary detaches admitted builtin values."""
import asyncio

import pytest

from orket.application.workflows import turn_read_context as reads
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import bind_logging, prepare_logging
from tests.helpers.application_root_controls import NativeHold
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.integration.test_bug_fix_event_inputs import records

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", ["none", "before", "after"])
async def test_missing_read_native_event_captures_nested_metadata(tmp_path, monkeypatch, stop, failure, record_property):
    native, hold = reads.log_event, NativeHold()
    native_failure = OSError("controlled required missing-read event failure")
    session, missing = {"trace": ["admitted"]}, ["expected.txt"]

    def held(*args):
        hold.wait()
        try:
            if failure == "before":
                raise native_failure
            native(*args)
            if failure == "after":
                raise native_failure
        finally:
            hold.finished.set()

    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await reads.publish_missing_read_event(issue_id="issue", role_name="reviewer", session_id=session,
                turn_index=1, missing_required_read_paths=missing, workspace=tmp_path / "workspace")

    monkeypatch.setattr(reads, "log_event", held)
    with bind_logging(await prepare_logging(LoggingInputs(tmp_path, timezone_name="MST"))):
        task = asyncio.create_task(dispatch())
        try:
            assert await asyncio.to_thread(hold.entered.wait, 3)
            assert await sqlite_response(tmp_path / "observer.sqlite", record_property) < 0.5
            session["trace"].append("late mutation")
            missing.append("late.txt")
            monkeypatch.chdir(tmp_path)
            monkeypatch.setenv("ORKET_TIMEZONE", "UTC")
            if stop == "timeout":
                deadline.reschedule(asyncio.get_running_loop().time() + 0.1)
            if stop == "cancel":
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
            await asyncio.sleep(0.15 if stop == "timeout" else 0)
            assert not task.done()
            hold.release.set()
            outcome, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            assert hold.finished.is_set() and not hold.expired
            if failure != "none":
                assert outcome is native_failure
            elif stop != "none":
                assert isinstance(outcome, asyncio.CancelledError if stop == "cancel" else TimeoutError)
            else:
                assert outcome is None
            rows = await records(tmp_path / "workspace/orket.log")
            assert len(rows) == int(failure != "before")
            if rows:
                assert rows[0]["data"]["session_id"] == {"trace": ["admitted"]}
                assert rows[0]["data"]["missing_required_read_paths"] == ["expected.txt"]
                assert rows[0]["data"]["missing_required_read_paths_count"] == 1
                assert rows[0]["timestamp"].endswith("-07:00")
        finally:
            hold.release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
