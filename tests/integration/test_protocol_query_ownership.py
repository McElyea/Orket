"""Layer: integration. Actual protocol files and API admission retain query workers."""
from __future__ import annotations

import asyncio
import threading
import time
from contextlib import suppress
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger, LedgerFramingError
from orket.application.services.protocol_replay_service import ProtocolReplayService
from orket.interfaces.routers.sessions import build_sessions_router
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from orket.runtime.protocol_replay import ProtocolReplayEngine
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.integration.test_api_active_request_ownership import serving_api
from tests.interfaces.test_sessions_router_protocol_replay import _seed_sqlite_run, _write_protocol_run

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
RESPONSIVENESS_SECONDS = 0.5


def _hold_replay(monkeypatch):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    replay = AppendOnlyRunLedger.replay_events

    def held(ledger, *args, **kwargs):
        entered.set()
        assert release.wait(5), "test must release the actual replay worker"
        try:
            return replay(ledger, *args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(AppendOnlyRunLedger, "replay_events", held)
    return entered, release, finished


async def test_cancelled_protocol_query_retains_actual_file_worker(tmp_path, monkeypatch):
    _write_protocol_run(tmp_path, "run-a", status="incomplete", ok=True)
    service = ProtocolReplayService(workspace_root=tmp_path)
    entered, release, finished = _hold_replay(monkeypatch)
    reading = asyncio.create_task(service.replay_protocol_run(run_id="run-a"))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        reading.cancel()
        await asyncio.sleep(0)
        reading.cancel()
        await asyncio.sleep(0)
        observed = (reading.done(), finished.is_set())
    finally:
        release.set()
        with suppress(asyncio.CancelledError):
            await reading
        assert await asyncio.to_thread(finished.wait, 3)
    assert observed == (False, False)


async def test_api_close_waits_for_protocol_replay_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    _write_protocol_run(tmp_path, "run-a", status="incomplete", ok=True)
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    async with serving_api(app) as client:
        owner = app.state.api_runtime_context
        entered, release, finished = _hold_replay(monkeypatch)
        request = asyncio.create_task(client.get("/v1/protocol/runs/run-a/replay"))
        closing = None
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            closing = asyncio.create_task(owner.close())
            with suppress(TimeoutError):
                await asyncio.wait_for(asyncio.shield(closing), RESPONSIVENESS_SECONDS)
            observed = (closing.done(), owner.closed, finished.is_set())
        finally:
            release.set()
            if closing is not None:
                await closing
            await request
            assert await asyncio.to_thread(finished.wait, 3)
    assert observed == (False, False, False)
    assert owner.closed and owner.active_request_count == 0


async def test_protocol_root_observation_keeps_event_loop_responsive(tmp_path, monkeypatch):
    _write_protocol_run(tmp_path, "run-a", status="incomplete", ok=True)
    service = ProtocolReplayService(workspace_root=tmp_path)
    entered, release = threading.Event(), threading.Event()
    resolve, loop_thread = Path.resolve, threading.get_ident()
    observed = {}

    def held(path, *args, **kwargs):
        if path == tmp_path / "runs" and not entered.is_set():
            observed.update(thread=threading.get_ident(), entered=time.monotonic())
            entered.set()
            assert release.wait(3)
        return resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", held)
    # A real independent timer bounds the old event-loop-blocking path so the
    # counterexample can settle; it is not the healthy responsiveness criterion.
    safety_release = threading.Timer(2, release.set)
    safety_release.start()
    reading = asyncio.create_task(service.replay_protocol_run(run_id="run-a"))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        elapsed = time.monotonic() - observed["entered"]
        observed["responsive"] = elapsed < RESPONSIVENESS_SECONDS
    finally:
        release.set()
        safety_release.cancel()
        await asyncio.to_thread(safety_release.join, 3)
        result = await reading
    assert result["session_id"] == "run-a"
    assert observed["thread"] != loop_thread and observed["responsive"]


async def test_empty_campaign_baseline_cannot_claim_match(tmp_path):
    events = tmp_path / "runs" / "empty" / "events.log"
    events.parent.mkdir(parents=True)
    events.touch()
    result = await ProtocolReplayService(workspace_root=tmp_path).compare_protocol_determinism_campaign(
        run_ids=["empty"], baseline_run="empty", runs_root=None,
    )
    assert result["all_match"] is False, result
    assert result["mismatch_count"] == 1
    assert result["comparisons"][0]["deterministic_match"] is False


async def test_api_parity_campaign_refuses_session_path_escape(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    workspace = tmp_path / "workspace"
    session_id = "../../outside"
    _write_protocol_run(workspace, session_id, status="incomplete", ok=True)
    database = workspace / ".orket/durable/db/orket_persistence.db"
    await _seed_sqlite_run(sqlite_db=database, session_id=session_id, status="incomplete")
    outside = tmp_path / "outside/events.log"
    original = outside.read_bytes()
    app = create_api_app(CompositionConfig(project_root=workspace))
    async with serving_api(app) as client:
        response = await client.get("/v1/protocol/ledger-parity/campaign", params={"session_id": session_id})
    assert outside.read_bytes() == original
    assert response.status_code == 400, response.text


async def test_cancelled_query_preserves_actual_ledger_failure(tmp_path, monkeypatch):
    _write_protocol_run(tmp_path, "run-a", status="incomplete", ok=True)
    events = tmp_path / "runs/run-a/events.log"
    events.write_bytes(b"corrupt frame\n")
    entered, release, finished = _hold_replay(monkeypatch)
    reading = asyncio.create_task(ProtocolReplayService(workspace_root=tmp_path).replay_protocol_run(run_id="run-a"))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        reading.cancel()
        await asyncio.sleep(0)
        assert not reading.done()
    finally:
        release.set()
        with pytest.raises(LedgerFramingError):
            await reading
    assert finished.is_set() and events.read_bytes() == b"corrupt frame\n"


async def test_parity_campaign_captures_requested_ids_before_worker(tmp_path, monkeypatch):
    _write_protocol_run(tmp_path, "run-a", status="incomplete", ok=True)
    database = tmp_path / ".orket/durable/db/orket_persistence.db"
    await _seed_sqlite_run(sqlite_db=database, session_id="run-a", status="incomplete")
    entered, release = threading.Event(), threading.Event()
    resolve = Path.resolve

    def held(path, *args, **kwargs):
        if path == tmp_path and not entered.is_set():
            entered.set()
            assert release.wait(5)
        return resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", held)
    ids = ["run-a"]
    reading = asyncio.create_task(ProtocolReplayService(workspace_root=tmp_path).compare_protocol_ledger_parity_campaign(
        session_ids=ids, sqlite_db_path=None, discover_limit=200,
    ))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        ids[:] = ["../../outside"]
    finally:
        release.set()
        result = await reading
    assert result["all_match"]
    assert result["requested_session_ids"] == ["run-a"] and result["candidate_count"] == 1


async def test_discovered_sqlite_session_escape_fails_before_file_read(tmp_path, monkeypatch):
    database = tmp_path / ".orket/durable/db/orket_persistence.db"
    await _seed_sqlite_run(sqlite_db=database, session_id="../../outside", status="incomplete")
    entered, release, _ = _hold_replay(monkeypatch)
    release.set()
    with pytest.raises(ValueError, match="Invalid run_id"):
        await ProtocolReplayService(workspace_root=tmp_path).compare_protocol_ledger_parity_campaign(
            session_ids=[], sqlite_db_path=None, discover_limit=200,
        )
    assert not entered.is_set()


@pytest.mark.parametrize("missing", [True, False])
async def test_direct_comparison_requires_observed_events(tmp_path, missing):
    events = tmp_path / "events.log"
    if not missing:
        events.touch()
    result = await asyncio.to_thread(ProtocolReplayEngine().compare_replays,
                                   run_a_events_path=events, run_b_events_path=events)
    assert not result["deterministic_match"]
    assert result["comparison_status"] == "insufficient_evidence"
    assert result["comparison_scope"] == "observed_protocol_state"
    assert result["event_count_a"] == result["event_count_b"] == 0
    assert result["differences"] == []


@pytest.mark.parametrize("linked_operand", ["events", "receipts", "artifact"])
async def test_api_replay_refuses_linked_file_outside_workspace(tmp_path, monkeypatch, linked_operand):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    workspace = tmp_path / "workspace"
    _write_protocol_run(workspace, "run-a", status="incomplete", ok=True)
    run = workspace / "runs/run-a"
    outside = tmp_path / "outside.txt"
    outside.write_text("outside evidence", encoding="utf-8")
    if linked_operand == "events":
        link = run / "events.log"
        link.unlink()
    elif linked_operand == "receipts":
        link = run / "receipts.log"
    else:
        link = run / "artifacts/linked.txt"
        link.parent.mkdir()
    link.symlink_to(outside)
    app = create_api_app(CompositionConfig(project_root=workspace))
    async with serving_api(app) as client:
        response = await client.get("/v1/protocol/runs/run-a/replay")
    assert response.status_code == 400, response.text
    assert outside.read_text(encoding="utf-8") == "outside evidence"


async def test_api_populated_comparison_reports_limited_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    for run_id in ("run-a", "run-b"):
        _write_protocol_run(tmp_path, run_id, status="incomplete", ok=True)
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    async with serving_api(app) as client:
        response = await client.get("/v1/protocol/replay/compare", params={"run_a": "run-a", "run_b": "run-b"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["deterministic_match"] and payload["comparison_status"] == "matched"
    assert payload["comparison_scope"] == "observed_protocol_state"
    assert payload["event_count_a"] == payload["event_count_b"] == 3
    assert payload["run_a"]["status"] == "incomplete"


async def test_default_router_root_resolves_only_in_query_worker(tmp_path, monkeypatch):
    _write_protocol_run(tmp_path, "run-a", status="incomplete", ok=True)
    app = FastAPI()
    app.include_router(build_sessions_router(
        turn_service_getter=lambda: None,
    ), prefix="/v1")
    monkeypatch.chdir(tmp_path)
    resolve, loop_thread = Path.resolve, threading.get_ident()
    threads = []

    def observed(path, *args, **kwargs):
        threads.append(threading.get_ident())
        return resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", observed)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://query.test") as client:
        response = await client.get("/v1/protocol/runs/run-a/replay")
    assert response.status_code == 200 and response.json()["session_id"] == "run-a"
    assert threads and loop_thread not in threads
