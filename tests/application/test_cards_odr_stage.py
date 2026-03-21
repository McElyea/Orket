from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.services.cards_odr_stage import _odr_prebuild_accepted, run_cards_odr_prebuild

pytestmark = pytest.mark.unit


class AsyncSpy:
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.return_value


def _issue() -> SimpleNamespace:
    issue = SimpleNamespace(
        id="ISSUE-1",
        name="Write agent_output/out.py",
        note="",
        params={},
    )
    issue.model_dump = lambda by_alias=True: {"id": issue.id, "name": issue.name, "params": dict(issue.params)}
    return issue


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_odr_prebuild_accepts_valid_decision_complete_max_rounds() -> None:
    assert _odr_prebuild_accepted(stop_reason="MAX_ROUNDS", odr_valid=True, pending_decisions=0) is True


def test_odr_prebuild_rejects_max_rounds_when_pending_decisions_remain() -> None:
    assert _odr_prebuild_accepted(stop_reason="MAX_ROUNDS", odr_valid=True, pending_decisions=1) is False


@pytest.mark.asyncio
async def test_run_cards_odr_prebuild_uses_issue_odr_max_rounds_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issue = _issue()
    issue.params["odr_max_rounds"] = 1
    save_spy = AsyncSpy(return_value=None)
    captured_kwargs: dict[str, object] = {}
    model_client = SimpleNamespace()

    async def _fake_live_refinement(**kwargs):
        captured_kwargs.update(kwargs)
        return {
            "task": str(kwargs["task"]),
            "rounds": [],
            "rounds_completed": 1,
            "stop_reason": "MAX_ROUNDS",
            "history_v": [],
            "history_rounds": [{"round": 1, "pending_decision_count": 0}],
            "final_requirement": "Write agent_output/out.py with a deterministic add(a, b) function.",
            "final_trace": {"pending_decision_count": 0, "validity_verdict": "valid"},
            "odr_valid": True,
            "odr_pending_decisions": 0,
            "odr_stop_reason": "MAX_ROUNDS",
        }

    monkeypatch.setattr("orket.application.services.cards_odr_stage.run_live_refinement", _fake_live_refinement)
    monkeypatch.setattr("orket.application.services.cards_odr_stage.log_event", lambda *_args, **_kwargs: None)

    summary = await run_cards_odr_prebuild(
        workspace=tmp_path,
        issue=issue,
        run_id="run-override",
        selected_model="qwen2.5-coder:7b",
        cards_runtime={
            "execution_profile": "odr_prebuild_builder_guard_v1",
            "artifact_contract": {
                "kind": "artifact",
                "primary_output": "agent_output/out.py",
                "required_write_paths": ["agent_output/out.py"],
                "required_read_paths": [],
            },
        },
        model_client=model_client,
        async_cards=SimpleNamespace(save=save_spy),
    )

    assert captured_kwargs["max_rounds"] == 1
    assert captured_kwargs["auditor_client"] is model_client
    assert summary["odr_max_rounds"] == 1
    assert summary["odr_accepted"] is True


@pytest.mark.asyncio
async def test_run_cards_odr_prebuild_records_completed_event_for_valid_max_rounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issue = _issue()
    save_spy = AsyncSpy(return_value=None)
    captured_events: list[tuple[str, dict[str, object]]] = []
    auditor_client = SimpleNamespace(provider=SimpleNamespace(model="qwen2.5:7b"))

    async def _fake_live_refinement(**kwargs):
        return {
            "task": str(kwargs["task"]),
            "rounds": [],
            "rounds_completed": 8,
            "stop_reason": "MAX_ROUNDS",
            "history_v": [],
            "history_rounds": [{"round": 8, "pending_decision_count": 0}],
            "final_requirement": "Write agent_output/out.py with a deterministic add(a, b) function.",
            "final_trace": {"pending_decision_count": 0, "validity_verdict": "valid"},
            "odr_valid": True,
            "odr_pending_decisions": 0,
            "odr_stop_reason": "MAX_ROUNDS",
        }

    def _capture_event(name: str, payload: dict[str, object], _workspace: Path) -> None:
        captured_events.append((name, payload))

    monkeypatch.setattr("orket.application.services.cards_odr_stage.run_live_refinement", _fake_live_refinement)
    monkeypatch.setattr("orket.application.services.cards_odr_stage.log_event", _capture_event)

    summary = await run_cards_odr_prebuild(
        workspace=tmp_path,
        issue=issue,
        run_id="run-1",
        selected_model="qwen2.5-coder:7b",
        cards_runtime={
            "execution_profile": "odr_prebuild_builder_guard_v1",
            "artifact_contract": {
                "kind": "artifact",
                "primary_output": "agent_output/out.py",
                "required_write_paths": ["agent_output/out.py"],
                "required_read_paths": [],
            },
        },
        model_client=SimpleNamespace(),
        auditor_client=auditor_client,
        async_cards=SimpleNamespace(save=save_spy),
    )

    assert summary["odr_accepted"] is True
    assert summary["odr_stop_reason"] == "MAX_ROUNDS"
    assert issue.params["odr_result"]["odr_accepted"] is True
    assert save_spy.calls
    assert captured_events[0][0] == "odr_prebuild_completed"
    artifact = _load_json(tmp_path / summary["odr_artifact_path"])
    assert artifact["accepted"] is True
    assert artifact["auditor_model"] == "qwen2.5:7b"
    assert artifact["odr_stop_reason"] == "MAX_ROUNDS"


@pytest.mark.asyncio
async def test_run_cards_odr_prebuild_retries_format_violation_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issue = _issue()
    save_spy = AsyncSpy(return_value=None)
    captured_events: list[tuple[str, dict[str, object]]] = []
    calls: list[dict[str, object]] = []

    async def _fake_live_refinement(**kwargs):
        calls.append(dict(kwargs))
        if len(calls) == 1:
            return {
                "task": str(kwargs["task"]),
                "rounds": [],
                "rounds_completed": 1,
                "stop_reason": "FORMAT_VIOLATION",
                "history_v": [],
                "history_rounds": [],
                "final_requirement": "",
                "final_trace": {"pending_decision_count": 0, "validity_verdict": "invalid"},
                "odr_valid": False,
                "odr_pending_decisions": 0,
                "odr_stop_reason": "FORMAT_VIOLATION",
                "odr_failure_mode": "format_violation",
            }
        return {
            "task": str(kwargs["task"]),
            "rounds": [],
            "rounds_completed": 1,
            "stop_reason": "MAX_ROUNDS",
            "history_v": [],
            "history_rounds": [{"round": 1, "pending_decision_count": 0}],
            "final_requirement": "Write agent_output/out.py with a deterministic add(a, b) function.",
            "final_trace": {"pending_decision_count": 0, "validity_verdict": "valid"},
            "odr_valid": True,
            "odr_pending_decisions": 0,
            "odr_stop_reason": "MAX_ROUNDS",
        }

    def _capture_event(name: str, payload: dict[str, object], _workspace: Path) -> None:
        captured_events.append((name, payload))

    monkeypatch.setattr("orket.application.services.cards_odr_stage.run_live_refinement", _fake_live_refinement)
    monkeypatch.setattr("orket.application.services.cards_odr_stage.log_event", _capture_event)

    summary = await run_cards_odr_prebuild(
        workspace=tmp_path,
        issue=issue,
        run_id="run-retry",
        selected_model="qwen2.5-coder:7b",
        cards_runtime={
            "execution_profile": "odr_prebuild_builder_guard_v1",
            "artifact_contract": {
                "kind": "artifact",
                "primary_output": "agent_output/out.py",
                "required_write_paths": ["agent_output/out.py"],
                "required_read_paths": [],
            },
        },
        model_client=SimpleNamespace(),
        async_cards=SimpleNamespace(save=save_spy),
        max_rounds=4,
    )

    assert len(calls) == 2
    assert calls[1]["max_rounds"] == 1
    assert summary["odr_accepted"] is True
    assert captured_events[0][0] == "odr_prebuild_format_violation_retry"
    assert captured_events[1][0] == "odr_prebuild_completed"
