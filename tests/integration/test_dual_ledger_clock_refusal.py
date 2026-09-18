"""Layer: integration. Backward supplied time cannot borrow the mirror's completion."""
import asyncio

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.application.services.dual_write_run_ledger import AsyncDualModeLedgerRepository
from orket.core.contracts.dual_write_intent import DualWriteLedgerError

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("primary", ["protocol", "sqlite"])
async def test_backward_protocol_time_retains_partial_effects_and_recovers_without_duplicate_events(tmp_path, primary):
    supplied = iter(["2030-01-01T00:00:01+00:00", "2030-01-01T00:00:00+00:00", "2030-01-01T00:00:02+00:00"])
    observed, telemetry = [], []

    def clock():
        value = next(supplied)
        observed.append(value)
        return value

    protocol = AsyncProtocolRunLedgerRepository(tmp_path / "protocol", timestamp_factory=clock)
    sqlite = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    repo = AsyncDualModeLedgerRepository(sqlite_repo=sqlite, protocol_repo=protocol, primary_mode=primary,
                                       telemetry_sink=lambda row: telemetry.append(dict(row)))
    await repo.start_run(session_id="clock-run", run_type="test", run_name="Clock", department="core", build_id="build")
    if primary == "protocol":
        with pytest.raises(DualWriteLedgerError, match="PRIMARY_UNAVAILABLE:ValueError:E_LEDGER_TIMESTAMP_NON_MONOTONIC"):
            await repo.finalize_run(session_id="clock-run", status="incomplete")
    else:
        await repo.finalize_run(session_id="clock-run", status="incomplete")
    assert (await sqlite.get_run("clock-run"))["status"] == "incomplete"
    assert (await protocol.get_run("clock-run"))["status"] == "running"
    assert [row["kind"] for row in await protocol.list_events("clock-run")] == ["run_started"]
    graph = tmp_path / "protocol/runs/clock-run/run_graph.json"
    assert not await asyncio.to_thread(graph.exists)
    pending, = await repo._load_intents()
    assert pending["sqlite_ack"] is True and pending["protocol_ack"] is False
    assert pending["protocol_error"] == "ValueError:E_LEDGER_TIMESTAMP_NON_MONOTONIC"
    assert any(row.get("kind") == "run_ledger_dual_write_parity" and row.get("parity_ok") is False
               for row in telemetry)
    await repo.initialize()
    await repo.initialize()
    assert (await repo.get_run("clock-run"))["status"] == "incomplete"
    events = await protocol.list_events("clock-run")
    assert [row["kind"] for row in events] == ["run_started", "run_finalized"]
    assert [row["timestamp"] for row in events] == [observed[0], observed[2]]
    assert len(observed) == 3 and await repo._load_intents() == []
    assert await asyncio.to_thread(graph.is_file)
