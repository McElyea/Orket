import pytest

from orket.application.services.bug_fix_phase_manager import BugFixPhaseManager
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock

pytestmark = pytest.mark.unit


class _FakeDb:
    def __init__(self) -> None:
        self.saved = []

    async def save_bug_fix_phase(self, phase):
        self.saved.append(phase)

    async def get_bug_fix_phase(self, rock_id):
        return self.saved[-1]


@pytest.mark.asyncio
async def test_bug_fix_phase_start_phase_logs_and_saves(monkeypatch, tmp_path):
    """Layer: unit. Controlled dependencies check event ordering, not live persistence."""
    captured = []

    def _fake_log_event(name, payload, workspace):
        captured.append((name, payload, workspace))

    monkeypatch.setattr("orket.application.services.bug_fix_phase_manager.log_event", _fake_log_event)
    db = _FakeDb()
    manager = BugFixPhaseManager(db=db, workspace=tmp_path, now_utc=ProtocolLedgerClock().utc_now)

    phase = await manager.start_phase("ROCK-123")

    assert phase.rock_id == "ROCK-123"
    assert db.saved and db.saved[0].rock_id == "ROCK-123"
    assert captured and captured[0][0] == "bug_fix_phase_started"
