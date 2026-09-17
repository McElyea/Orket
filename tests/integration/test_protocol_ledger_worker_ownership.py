"""Protocol receipt writes retain their worker and captured caller inputs."""
import asyncio
import threading
import time

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_receipt_writer(repository, monkeypatch):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = repository._append_receipt_sync

    def held(*arguments):
        entered.set()
        assert release.wait(10)
        try:
            return original(*arguments)
        finally:
            finished.set()

    monkeypatch.setattr(repository, "_append_receipt_sync", held)
    return entered, release, finished


@pytest.mark.parametrize("mode", ["cancel", "timeout"])
# Layer: integration
async def test_receipt_write_retains_worker_and_repository_lock(tmp_path, monkeypatch, mode):
    repository = AsyncProtocolRunLedgerRepository(tmp_path)
    entered, release, finished = hold_receipt_writer(repository, monkeypatch)

    async def invoke():
        if mode == "timeout":
            async with asyncio.timeout(0.1):
                await repository.append_receipt(session_id="receipt-owner", receipt={"value": "retained"})
        else:
            await repository.append_receipt(session_id="receipt-owner", receipt={"value": "retained"})

    task = asyncio.create_task(invoke())
    reader = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if mode == "cancel":
            task.cancel()
        await asyncio.sleep(0.15)
        reader = asyncio.create_task(repository.list_receipts("receipt-owner"))
        started = time.perf_counter()
        await asyncio.sleep(0)
        assert time.perf_counter() - started < 0.5  # Predeclared D responsiveness bound.
        await asyncio.sleep(0.05)
        assert not task.done(), "Interrupted caller abandoned its still-running receipt writer"
        assert not reader.done(), "Repository lock escaped before the writer settled"
    finally:
        release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await task
        assert await asyncio.to_thread(finished.wait, 5)
        if reader is not None:
            await reader
    rows = await AsyncProtocolRunLedgerRepository(tmp_path).list_receipts("receipt-owner")
    assert len(rows) == 1 and rows[0]["value"] == "retained"


# Layer: integration
async def test_receipt_write_captures_nested_input_before_worker(tmp_path, monkeypatch):
    repository = AsyncProtocolRunLedgerRepository(tmp_path)
    entered, release, finished = hold_receipt_writer(repository, monkeypatch)
    payload = {"result": {"values": ["original"]}}
    task = asyncio.create_task(repository.append_receipt(session_id="receipt-input", receipt=payload))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        payload["result"]["values"][0] = "mutated-after-admission"
    finally:
        release.set()
        await task
        assert finished.is_set()
    rows = await AsyncProtocolRunLedgerRepository(tmp_path).list_receipts("receipt-input")
    assert rows[0]["result"] == {"values": ["original"]}


@pytest.mark.parametrize("operation", ["start", "finalize", "append"])
# Layer: integration
async def test_event_write_captures_nested_inputs_before_first_io(tmp_path, monkeypatch, operation):
    repository = AsyncProtocolRunLedgerRepository(tmp_path)
    arguments = dict(session_id="event-input", run_type="epic", run_name="capture", department="core", build_id="b1")
    if operation != "start":
        await repository.start_run(**arguments)
    entered, release = threading.Event(), threading.Event()
    original = AppendOnlyRunLedger.replay_events

    def held(ledger):
        entered.set()
        assert release.wait(10)
        return original(ledger)

    monkeypatch.setattr(AppendOnlyRunLedger, "replay_events", held)
    payload = {"value": {"items": ["original"]}}
    if operation == "start":
        request = repository.start_run(**arguments, summary=payload)
    elif operation == "finalize":
        request = repository.finalize_run(session_id="event-input", status="done", summary=payload)
    else:
        request = repository.append_event(session_id="event-input", kind="diagnostic", payload=payload)
    task = asyncio.create_task(request)
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        payload["value"]["items"][0] = "mutated-after-admission"
    finally:
        release.set()
        await task
    row = (await AsyncProtocolRunLedgerRepository(tmp_path).list_events("event-input"))[-1]
    captured = row if operation == "append" else row["summary"]
    assert captured["value"] == {"items": ["original"]}
