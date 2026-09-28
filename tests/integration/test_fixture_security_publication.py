"""Layer: integration. Required security log ownership over real native append."""
from __future__ import annotations

import asyncio
import json
import threading
from types import SimpleNamespace

import pytest

from orket.adapters.observability import log_publication
from orket.application.services.fixture_verification_service import FixtureVerificationService
from orket.core.domain.fixture_verifier import VerificationSecurityError
from orket.core.runtime_event import RUNTIME_EVENT_SCHEMA_VERSION
from tests.helpers.fixture_input_controls import prepare_native, selected_time
from tests.helpers.runtime_verification_hold import settle, sqlite_response, wait_entered

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_security_append(monkeypatch, failure):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            expired=False, thread=None, paths=[])
    original = log_publication._append_line_sync

    def held(path, line):
        if json.loads(line).get("event") != "verification_security_violation":
            return original(path, line)
        state.paths.append(path)
        state.thread = threading.get_ident()
        state.entered.set()
        try:
            state.expired = not state.release.wait(5)
            assert not state.expired, "required publication release missing"
            original(path, line)  # A failing acknowledgement may follow real append.
            if failure is not None:
                raise failure
        finally:
            state.finished.set()

    monkeypatch.setattr(log_publication, "_append_line_sync", held)
    return state


def assert_security_record(record):
    assert set(record) == {"timestamp", "level", "role", "event", "data"}
    assert record["level"] == "info" and record["role"] == "system"
    assert set(record["data"]) == {"fixture_path", "runtime_event"}
    assert record["data"]["fixture_path"] == "../outside.py"
    canonical = record["data"]["runtime_event"]
    assert canonical["schema_version"] == RUNTIME_EVENT_SCHEMA_VERSION
    assert canonical["event"] == record["event"] and canonical["role"] == "system"
    assert canonical["session_id"] == canonical["issue_id"] == "" and canonical["duration_ms"] is None


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("fails", [False, True])
async def test_security_publication_retains_native_append_and_failure_precedence(
    tmp_path, monkeypatch, record_property, stop, fails,
):
    selected, later = tmp_path / "selected", tmp_path / "later"
    verification = await asyncio.to_thread(prepare_native, selected)
    verification.fixture_path = "../outside.py"
    failure = OSError("controlled required security append acknowledgement failure") if fails else None
    hold = hold_security_append(monkeypatch, failure)
    service = FixtureVerificationService(selected, utc_now=selected_time, environment={})
    task = asyncio.create_task(service.verify(verification))
    waiter = None
    try:
        await wait_entered(hold)
        service.workspace, verification.fixture_path = later, "verification/mutated.py"
        if stop == "cancel":
            task.cancel("first required-publication interruption")
            await asyncio.sleep(0)
            task.cancel("repeated required-publication interruption")
        elif stop == "timeout":
            waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
            await asyncio.sleep(0.04)
        assert await sqlite_response(tmp_path / "response.sqlite3", record_property) < 0.5
        assert not task.done() and (waiter is None or not waiter.done())
        hold.release.set()
        expected = OSError if fails else {"none": VerificationSecurityError, "cancel": asyncio.CancelledError,
                                         "timeout": TimeoutError}[stop]
        with pytest.raises(expected) as caught:
            await (waiter if waiter is not None else task)
        if fails:
            assert caught.value is failure
        assert hold.finished.is_set() and not hold.expired and hold.thread != threading.get_ident()
        rows = (await asyncio.to_thread((selected / "orket.log").read_text, encoding="utf-8")).splitlines()
        records = [json.loads(row) for row in rows]
        assert len(records) == 1 and records[0]["event"] == "verification_security_violation"
        assert_security_record(records[0])
        assert not await asyncio.to_thread((later / "orket.log").exists)
        assert verification.scenarios[0].status == "pending" and verification.last_run is None
        assert not await asyncio.to_thread((selected / "verification/observed.json").exists)
        record_property("required_security_publication", json.dumps({"path": str(selected / "orket.log"),
            "stop": stop, "failed_acknowledgement": fails, "settled": hold.finished.is_set(),
            "native_thread": hold.thread != threading.get_ident(), "captured_record": records[0]}))
    finally:
        await settle(task, hold)
        if waiter is not None:
            await asyncio.gather(waiter, return_exceptions=True)
