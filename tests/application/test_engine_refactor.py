import pytest
from pathlib import Path

from orket.orchestration.engine import OrchestrationEngine


class _FakePipeline:
    def __init__(self):
        self.calls = []

    async def run_epic(self, epic_id, build_id=None, session_id=None, driver_steered=False):
        self.calls.append(("run_epic", epic_id, build_id, session_id, driver_steered))
        return []

    async def run_rock(self, rock_id, build_id=None, session_id=None, driver_steered=False):
        self.calls.append(("run_rock", rock_id, build_id, session_id, driver_steered))
        return {}

    async def run_card(self, card_id, build_id=None, session_id=None, driver_steered=False, target_issue_id=None):
        self.calls.append(("run_card", card_id, build_id, session_id, driver_steered, target_issue_id))
        return []


class _FakeLoader:
    def __init__(self, *_args, **_kwargs):
        pass

    def load_organization(self):
        return None


@pytest.mark.asyncio
async def test_engine_explicit_calls(monkeypatch):
    workspace = Path("./test_workspace")
    fake_pipeline = _FakePipeline()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orket.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orket.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    engine = OrchestrationEngine(workspace)

    await engine.run_epic("my-epic")
    await engine.run_rock("my-rock")
    await engine.run_issue("my-issue")

    assert ("run_epic", "my-epic", None, None, False) in fake_pipeline.calls
    assert ("run_rock", "my-rock", None, None, False) in fake_pipeline.calls
    assert ("run_card", "my-issue", None, None, False, None) in fake_pipeline.calls


@pytest.mark.asyncio
async def test_engine_run_card_deprecated(monkeypatch):
    workspace = Path("./test_workspace")
    fake_pipeline = _FakePipeline()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orket.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orket.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    engine = OrchestrationEngine(workspace)

    await engine.run_card("some-card", target_issue_id="I1")

    assert ("run_card", "some-card", None, None, False, "I1") in fake_pipeline.calls

