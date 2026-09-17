"""The application wake boundary persists its explicitly supplied clock."""
import pytest

from orket.adapters.storage.async_governed_agent_wake_repository import AsyncGovernedAgentWakeRepository
from orket.application.services.governed_agent_wake_commands import build_governed_agent_wake_commands
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock
from tests.runtime.governed_agent_test_support import agent_request

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
async def test_manual_wake_application_uses_supplied_clock_and_reopens_same_value(tmp_path):
    clock = ProtocolLedgerClock()
    clock.current = clock.current.replace(year=2041)
    commands = build_governed_agent_wake_commands(tmp_path / "wake.sqlite3", runtime_inputs=clock)
    payload = {
        "occurrence_id": "clock-input", "target_kind": "new_run", "target_run_id": None,
        "workload_id": "governed-agent-loop", "dispatch": {
            "schema_version": "governed_agent_wake_dispatch.v1", "request": agent_request(),
            "creation_timestamp_utc": "2041-01-01T00:00:00Z",
            "decision_timestamps_utc": ["2041-01-01T00:00:01Z", "2041-01-01T00:00:02Z"],
            "next_lease_expiries_utc": ["2041-01-01T00:00:07Z"],
        },
    }
    first = await commands.enqueue(payload)
    repeated = await commands.enqueue(payload)
    assert repeated["status"] == "idempotent" and repeated["wake"] == first["wake"]
    reopened = await AsyncGovernedAgentWakeRepository(tmp_path / "wake.sqlite3").get_wake(
        wake_id=first["wake"]["wake_id"],
    )
    assert reopened.created_at_utc == "2041-01-01T00:00:00.000000Z"
