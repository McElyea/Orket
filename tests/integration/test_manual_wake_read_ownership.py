"""Integration: manual wake commands retain request reads and admitted CLI arguments."""
import argparse
import asyncio
import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_governed_agent_wake_repository import AsyncGovernedAgentWakeRepository
from orket.application.services.governed_agent_wake_commands import build_governed_agent_wake_commands
from orket.interfaces.governed_agent_wake_cli import run_governed_agent_wake_command
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock
from tests.helpers.runtime_verification_hold import hold_stream
from tests.integration.test_governed_demo_ownership import observe_held
from tests.integration.test_marshaller_attempt_ownership import hold_native
from tests.integration.test_marshaller_publication_ownership import assert_outcome, roots
from tests.runtime.governed_agent_test_support import agent_request

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("operation", ["resolve", "read", "close"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_manual_wake_request_retains_native_inputs(tmp_path, monkeypatch, operation, stop, failure, record_property):
    first, other = await roots(tmp_path)
    request = first / "request.json"
    original = agent_request()
    await asyncio.to_thread(request.write_text, json.dumps(original), encoding="utf-8")
    await asyncio.to_thread((other / request.name).write_text, "[]", encoding="utf-8")
    database = first / "wake.sqlite3"
    commands = build_governed_agent_wake_commands(database, runtime_inputs=ProtocolLedgerClock())
    assert (await commands.list_wakes(target_run_id=None))["items"] == []
    args = argparse.Namespace(agent_wake_command="enqueue", request="request.json", run_id=None,
        workload_id="governed-agent-loop", occurrence_id="admitted-occurrence",
        creation_timestamp_utc="2041-01-01T00:00:00Z",
        decision_timestamp_utc=["2041-01-01T00:00:01Z", "2041-01-01T00:00:02Z"],
        next_lease_expires_at_utc=["2041-01-01T00:00:07Z"])
    monkeypatch.chdir(first)
    hold = (hold_native(monkeypatch, Path, "resolve", lambda path, *a, **kw: path.name == request.name, failure)
            if operation == "resolve" else hold_stream(monkeypatch, request, operation, failure=failure))
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await run_governed_agent_wake_command(args, commands)

    task = asyncio.create_task(dispatch())
    try:
        assert await asyncio.to_thread(hold.entered.wait, 3)
        args.occurrence_id = "late-occurrence"
        args.run_id = "late-run"
        args.workload_id = None
        args.creation_timestamp_utc = "2050-01-01T00:00:00Z"
        args.decision_timestamp_utc[:] = ["2050-01-01T00:00:01Z"]
        args.next_lease_expires_at_utc[:] = ["2050-01-01T00:00:07Z"]
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        assert_outcome(result, stop, failure)
        wakes = await AsyncGovernedAgentWakeRepository(database).list_wakes(target_run_id=None)
        assert len(wakes) == int(stop == "none" and not failure)
        if wakes:
            wake = wakes[0]
            assert result["status"] == "enqueued" and wake.occurrence_id == "admitted-occurrence"
            assert wake.target_kind == "new_run" and wake.workload_id == "governed-agent-loop"
            assert wake.payload["request"] == original
            assert wake.payload["creation_timestamp_utc"] == "2041-01-01T00:00:00Z"
            assert wake.payload["decision_timestamps_utc"] == ["2041-01-01T00:00:01Z", "2041-01-01T00:00:02Z"]
            assert wake.payload["next_lease_expiries_utc"] == ["2041-01-01T00:00:07Z"]
        assert all(stream.closed for stream in getattr(hold, "streams", []))
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
