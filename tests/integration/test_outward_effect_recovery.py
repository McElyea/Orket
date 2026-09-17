"""Layer: integration. Actual commands, SQLite failures, and terminated API processes."""

from __future__ import annotations

import asyncio
import sys

import pytest

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from tests.helpers.outward_authorization import (
    append_command,
    approve,
    approve_in_new_process,
    effect_snapshot,
    outward_api,
    submit_sequence,
)
from tests.helpers.outward_authorization import boundary as boundary


@pytest.mark.integration
@pytest.mark.parametrize("checkpoint", ["claim", "intent", "dispatch", "receipt", "publication"])
# Layer: integration
async def test_process_death_never_reexecutes_uncertain_or_observed_command(tmp_path, boundary, monkeypatch, checkpoint):
    """Layer: integration. Kill an isolated API process, then retry through a new application."""
    db_path, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "tests.helpers.outward_effect_worker", str(tmp_path), proposal_id, checkpoint,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        while True:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=20)
            assert line, (await process.stderr.read()).decode()
            if line.decode().strip() == "BT1_EFFECT_CHECKPOINT=" + checkpoint:
                break
    finally:
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(process.communicate(), timeout=10)
    effect, journal = await effect_snapshot(db_path, proposal_id)
    before = effect.state
    async with outward_api(tmp_path, inputs) as (client, _context):
        retried = await approve(client, proposal_id)
        again = await approve(client, proposal_id)
    allowed = checkpoint in {"receipt", "publication"}
    assert retried.status_code == again.status_code == (200 if allowed else 409), retried.text
    effect, after_journal = await effect_snapshot(db_path, proposal_id)
    assert effect.state == ("published" if allowed else before)
    if not allowed:
        assert after_journal == journal
    target = tmp_path / "effects.txt"
    if checkpoint in {"dispatch", "receipt", "publication"}:
        assert target.read_text().splitlines() == ["effect"]
    else:
        assert not target.exists()
    events = await OutwardRunEventStore(db_path).list_for_run("bt0-run")
    assert len([event for event in events if event.event_type == "tool_invoked"]) == int(allowed)


@pytest.mark.integration
# Layer: integration
async def test_receipt_republication_after_ledger_failure_does_not_redispatch(tmp_path, boundary, monkeypatch):
    """Layer: integration. A SQLite abort after the actual effect retains its receipt for publication retry."""
    db_path, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
        async with connect_sqlite_wal(db_path) as conn:
            await conn.execute("""CREATE TRIGGER bt1_effect_publish_abort BEFORE INSERT ON run_events
                WHEN NEW.event_type = 'tool_invoked' BEGIN SELECT RAISE(ABORT, 'bt1 publication failure'); END""")
            await conn.commit()
        failed = await approve(client, proposal_id)
        assert failed.status_code == 500
    effect, _journal = await effect_snapshot(db_path, proposal_id)
    assert effect.state == "observed" and effect.receipt["result"]["returncode"] == 0
    retained_receipt, retained_digest = effect.receipt, effect.receipt_digest
    assert retained_receipt["event"]["timing"]["status"] == "measured"
    assert retained_receipt["event"]["duration_ms"] > 0
    assert (await OutwardRunStore(db_path).get("bt0-run")).current_turn == 1
    async with connect_sqlite_wal(db_path) as conn:
        await conn.execute("DROP TRIGGER bt1_effect_publish_abort")
        await conn.commit()
    async with outward_api(tmp_path, inputs) as (client, _context):
        retried = await approve(client, proposal_id)
        assert retried.status_code == 200, retried.text
    assert (await asyncio.to_thread((tmp_path / "effects.txt").read_text)).splitlines() == ["effect"]
    assert (await OutwardRunStore(db_path).get("bt0-run")).status == "completed"
    effect, journal = await effect_snapshot(db_path, proposal_id)
    assert effect.state == "published" and len(journal) == 4
    assert effect.receipt == retained_receipt and effect.receipt_digest == retained_digest
    events = await OutwardRunEventStore(db_path).list_for_run("bt0-run")
    invoked, = [event for event in events if event.event_type == "tool_invoked"]
    assert invoked.payload == retained_receipt["event"]


@pytest.mark.integration
# Layer: integration
async def test_two_api_processes_cannot_share_a_dispatch_claim(tmp_path, boundary, monkeypatch):
    """Layer: integration. Hold one process after intent, reject a competing process, then observe one append."""
    db_path, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "tests.helpers.outward_effect_worker", str(tmp_path), proposal_id, "intent",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        while True:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=20)
            assert line, (await process.stderr.read()).decode()
            if line.decode().strip() == "BT1_EFFECT_CHECKPOINT=intent":
                break
        status, payload = await approve_in_new_process(tmp_path, proposal_id, "approve")
        assert status == 409 and payload["detail"] == "E_OUTWARD_EFFECT_IN_FLIGHT_OR_UNCERTAIN"
        assert not (tmp_path / "effects.txt").exists()
        stdout, stderr = await asyncio.wait_for(process.communicate(b"continue\n"), timeout=20)
        assert process.returncode == 0, stderr.decode()
        assert 'BT1_RESPONSE=[200,' in stdout.decode()
    finally:
        if process.returncode is None:
            process.kill()
            await process.communicate()
    assert (tmp_path / "effects.txt").read_text().splitlines() == ["effect"]
    effect, journal = await effect_snapshot(db_path, proposal_id)
    assert effect.state == "published" and len(journal) == 4
