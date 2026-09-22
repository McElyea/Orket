"""Layer: integration. Replay observations own actual artifact reads through interruption."""

import asyncio
import json
import threading

import pytest

from orket.orchestration.engine_services import ReplayDiagnosticsService
from scripts.audit.replay_turn import replay_turn_report
from tests.helpers.kernel_state_probe import responsive_sqlite

pytestmark = pytest.mark.integration


@pytest.fixture
def replay_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / "durable"))
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    workspace = tmp_path / "workspace"
    turn = workspace / "observability/session/issue/001_coder"
    turn.mkdir(parents=True)
    for name, value in {
        "checkpoint.json": {"model": "fixture-model", "role": "coder"},
        "messages.json": [{"role": "user", "content": "Retained fixture prompt"}],
        "parsed_tool_calls.json": [],
    }.items():
        (turn / name).write_text(json.dumps(value), encoding="utf-8")
    (turn / "model_response.txt").write_text("fixture response", encoding="utf-8")
    return workspace


async def replay_fixture(**request):
    assert request["messages"] == [{"role": "user", "content": "Retained fixture prompt"}]
    return {"content": "fixture response", "raw": {"provider": "protocol-fixture"}}


def test_replay_diagnostics_refuses_loop_before_artifact_observation(replay_artifacts):
    service = ReplayDiagnosticsService(replay_artifacts)

    async def observe():
        with pytest.raises(RuntimeError, match="E_REPLAY_OBSERVATION_REQUIRES_ASYNC_OWNER"):
            service.replay_turn_diagnostics(session_id="session", issue_id="issue", turn_index=1)

    asyncio.run(observe())


def test_replay_report_is_read_only_without_runtime_construction(replay_artifacts, tmp_path):
    before = {p.relative_to(replay_artifacts): p.read_bytes() for p in replay_artifacts.rglob("*") if p.is_file()}
    result = asyncio.run(
        replay_turn_report(
            workspace=replay_artifacts, session_id="session", issue_id="issue", turn_index=1, replay_call=replay_fixture
        )
    )
    after = {p.relative_to(replay_artifacts): p.read_bytes() for p in replay_artifacts.rglob("*") if p.is_file()}
    assert result["stability_status"] == "stable" and result["structural_verdict"]["match"]
    assert after == before and not (tmp_path / "durable").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("interruption", ["cancel", "timeout", "read-failure"])
async def test_replay_read_stays_owned_until_native_observation_settles(
    replay_artifacts, tmp_path, monkeypatch, record_property, interruption
):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = ReplayDiagnosticsService.replay_turn_diagnostics

    def observe(owner, **kwargs):
        entered.set()
        try:
            assert release.wait(10)
            if interruption == "read-failure":
                return (tmp_path / "missing-read-input").read_bytes()
            return original(owner, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(ReplayDiagnosticsService, "replay_turn_diagnostics", observe)
    task = asyncio.create_task(
        replay_turn_report(
            workspace=replay_artifacts, session_id="session", issue_id="issue", turn_index=1, replay_call=replay_fixture
        )
    )
    waiter = None
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 10), 10)
        if interruption == "timeout":
            waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
        else:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(0.04)
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        assert not task.done() and not finished.is_set()
        release.set()
        results = await asyncio.wait_for(
            asyncio.gather(task, *([waiter] if waiter else []), return_exceptions=True), 10
        )
        assert isinstance(results[0], OSError if interruption == "read-failure" else asyncio.CancelledError)
        if waiter:
            assert isinstance(results[1], TimeoutError)
        assert finished.is_set()
    finally:
        release.set()
        await asyncio.gather(task, *([waiter] if waiter else []), return_exceptions=True)
        assert await asyncio.wait_for(asyncio.to_thread(finished.wait, 10), 10)
