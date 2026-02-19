import pytest

from orket.domain.bug_fix_phase import BugFixPhaseManager


class _FakeDb:
    def __init__(self) -> None:
        self.saved = []

    async def save_bug_fix_phase(self, phase):
        self.saved.append(phase)


@pytest.mark.asyncio
async def test_bug_fix_phase_start_phase_logs_and_saves(monkeypatch):
    captured = []

    def _fake_log_event(name, payload, workspace):
        captured.append((name, payload, workspace))

    monkeypatch.setattr("orket.domain.bug_fix_phase.log_event", _fake_log_event)
    db = _FakeDb()
    manager = BugFixPhaseManager(db=db)

    phase = await manager.start_phase("ROCK-123")

    assert phase.rock_id == "ROCK-123"
    assert db.saved and db.saved[0].rock_id == "ROCK-123"
    assert captured and captured[0][0] == "bug_fix_phase_started"
