from types import SimpleNamespace

import pytest

from orket.orchestration.orchestrator import Orchestrator
from orket.schema import VerificationResult


class _FakeCards:
    def __init__(self):
        self.saved = None

    async def get_by_id(self, _issue_id):
        return SimpleNamespace(
            model_dump=lambda: {
                "id": "I1",
                "summary": "Issue 1",
                "seat": "dev",
                "verification": {
                    "fixture_path": None,
                    "scenarios": [],
                },
            }
        )

    async def save(self, record):
        self.saved = record


class _FakeRegistry:
    def get(self, _sandbox_id):
        return None


class _FakeSandboxOrchestrator:
    def __init__(self):
        self.registry = _FakeRegistry()


@pytest.mark.asyncio
async def test_verify_issue_uses_to_thread(monkeypatch, tmp_path):
    cards = _FakeCards()
    orchestrator = Orchestrator(
        workspace=tmp_path / "workspace",
        async_cards=cards,
        snapshots=None,
        org=None,
        config_root=tmp_path,
        db_path=str(tmp_path / "test.db"),
        loader=None,
        sandbox_orchestrator=_FakeSandboxOrchestrator(),
    )

    called = {"to_thread": False, "verify": False}
    expected = VerificationResult(timestamp="2026-02-11T00:00:00+00:00", total_scenarios=0, passed=0, failed=0, logs=[])

    def fake_verify(_verification, _workspace):
        called["verify"] = True
        return expected

    async def fake_to_thread(func, *args, **kwargs):
        called["to_thread"] = True
        return func(*args, **kwargs)

    monkeypatch.setattr("orket.domain.verification.VerificationEngine.verify", fake_verify, raising=False)
    monkeypatch.setattr("orket.orchestration.orchestrator.asyncio.to_thread", fake_to_thread, raising=False)

    result = await orchestrator.verify_issue("I1")

    assert called["to_thread"] is True
    assert called["verify"] is True
    assert result == expected
    assert cards.saved is not None
