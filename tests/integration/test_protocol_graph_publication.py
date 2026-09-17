"""Graph files attest to observed terminal ledger events and verified publication."""
import asyncio
import json
import threading
from pathlib import Path

import pytest

import orket.adapters.storage.async_protocol_run_ledger as ledger_module
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.adapters.storage.run_graph_artifact import reconstruct_run_graph_from_events_log
from orket.core.contracts.protocol_error_codes import is_registered_protocol_error_code
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock

pytestmark = pytest.mark.integration


async def started(root):
    clock = ProtocolLedgerClock()
    repo = AsyncProtocolRunLedgerRepository(root, timestamp_factory=clock.utc_now_iso)
    await repo.start_run(session_id="graph-run", run_type="test", run_name="Graph", department="core", build_id="build")
    return repo, root / "runs/graph-run/run_graph.json"


@pytest.mark.asyncio
async def test_refused_terminal_event_cannot_publish_a_future_graph(tmp_path):
    """Layer: integration. Timestamp refusal leaves no graph of an uncommitted terminal event."""
    repo, graph = await started(tmp_path)
    with pytest.raises(ValueError, match="E_LEDGER_TIMESTAMP_NON_MONOTONIC"):
        await repo.finalize_run(session_id="graph-run", status="incomplete", finalized_at="2025-01-01T00:00:00+00:00")
    assert not await asyncio.to_thread(graph.exists)
    assert not any(row["kind"] == "run_finalized" for row in await repo.list_events("graph-run"))


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
async def test_terminal_retry_repairs_the_derived_graph_without_duplicate_ledger_event(tmp_path, damage):
    """Layer: integration. Real missing/corrupt graph files are repaired from the retained ledger."""
    repo, graph = await started(tmp_path)
    terminal = await repo.finalize_run(session_id="graph-run", status="incomplete")
    expected = await asyncio.to_thread(graph.read_bytes)
    if damage == "missing":
        await asyncio.to_thread(graph.unlink)
    else:
        await asyncio.to_thread(graph.write_bytes, b"corrupt projection")
    retried = await repo.finalize_run(session_id="graph-run", status="incomplete")
    assert retried == terminal
    assert await asyncio.to_thread(graph.read_bytes) == expected
    assert sum(row["kind"] == "run_finalized" for row in await repo.list_events("graph-run")) == 1


@pytest.mark.asyncio
async def test_graph_worker_cancellation_retains_the_observed_terminal_event(tmp_path, monkeypatch):
    """Layer: integration. An admitted writer settles through repeated cancellation; its ledger already agrees."""
    repo, graph = await started(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = ledger_module.write_run_graph_artifact

    def held_write(**kwargs):
        entered.set()
        assert release.wait(5), "fixture publication was never released"
        return original(**kwargs)

    monkeypatch.setattr(ledger_module, "write_run_graph_artifact", held_write)
    task = asyncio.create_task(repo.finalize_run(session_id="graph-run", status="incomplete"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        loop = asyncio.get_running_loop()
        began = loop.time()
        await asyncio.wait_for(asyncio.sleep(0.01), 0.5)
        assert loop.time() - began < 0.5
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        events = await repo.list_events("graph-run")
        assert sum(row["kind"] == "run_finalized" for row in events) == 1
        payload = json.loads(await asyncio.to_thread(graph.read_text, encoding="utf-8"))
        assert payload["derived_from"]["ledger_event_count"] == len(events)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_graph_publication_detects_changed_bytes_and_retry_repairs_them(tmp_path, monkeypatch):
    """Layer: integration. Controlled concurrent disk mutation cannot become verified publication."""
    repo, graph = await started(tmp_path)
    original = Path.read_bytes
    tampered = []

    def changed_read(path):
        if path == graph and not tampered:
            path.write_bytes(b"changed during publication")
            tampered.append(True)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", changed_read)
    with pytest.raises(OSError, match="E_FILE_WRITE_UNVERIFIED") as error:
        await repo.finalize_run(session_id="graph-run", status="incomplete")
    assert is_registered_protocol_error_code(str(error.value))
    assert tampered
    assert (await repo.get_run("graph-run"))["status"] == "incomplete"
    await repo.finalize_run(session_id="graph-run", status="incomplete")
    payload = json.loads(await asyncio.to_thread(graph.read_text, encoding="utf-8"))
    assert payload["run_id"] == "graph-run"
    assert sum(row["kind"] == "run_finalized" for row in await repo.list_events("graph-run")) == 1


@pytest.mark.asyncio
async def test_graph_log_replay_retains_its_worker_and_loop_responsiveness(tmp_path, monkeypatch):
    """Layer: integration. A blocked real-file reader remains owned within a 0.5-second loop bound."""
    repo, _ = await started(tmp_path)
    await repo.finalize_run(session_id="graph-run", status="incomplete")
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = AppendOnlyRunLedger.replay_events

    def held_read(ledger):
        entered.set()
        assert release.wait(5)
        events = original(ledger)
        finished.set()
        return events

    monkeypatch.setattr(AppendOnlyRunLedger, "replay_events", held_read)
    task = asyncio.create_task(reconstruct_run_graph_from_events_log(
        events_log_path=tmp_path / "runs/graph-run/events.log"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        loop = asyncio.get_running_loop()
        began = loop.time()
        await asyncio.wait_for(asyncio.sleep(0.01), 0.5)
        assert loop.time() - began < 0.5
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert finished.is_set()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
