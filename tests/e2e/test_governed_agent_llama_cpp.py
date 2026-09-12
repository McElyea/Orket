# Layer: end-to-end
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orket.interfaces.api import create_api_app
from tests.e2e.test_governed_agent_effect_ollama import _run_effect_resolution
from tests.e2e.test_governed_agent_ollama import _assert_measured_receipts, _receipts, _run_live
from tests.e2e.test_governed_agent_supervisor_ollama import (
    _configure_api,
    _headers,
    _wait_for_terminal_wake,
    _wake_payload,
    _write_catalog,
)

pytestmark = [
    pytest.mark.end_to_end,
    pytest.mark.skipif(os.getenv("ORKET_RUN_LIVE_AGENT_LLAMA_CPP") != "1", reason="requires live llama.cpp"),
]


def _model() -> str:
    model = os.getenv("ORKET_GOVERNED_AGENT_MODEL", "").strip()
    assert model, "Set ORKET_GOVERNED_AGENT_MODEL to an exact inventoried, served GGUF alias"
    return model


@pytest.mark.parametrize("case_id", ["mixed", "all-open", "empty-first"])
def test_live_llama_cpp_cli_continuation(tmp_path: Path, capsys, monkeypatch, case_id: str) -> None:
    """Layer: end-to-end. Real inference and external children reach verified final truth."""
    payload = _run_live(tmp_path, capsys, monkeypatch, models={"default": _model()},
                        case_id=case_id, provider=None if case_id == "mixed" else "llama_cpp")
    assert payload["observed_path"] == "primary"
    assert payload["observed_result"] == "success"
    assert [item["disposition"] for item in payload["decisions"]] == ["continue", "complete"]
    receipts = _receipts(payload)
    _assert_measured_receipts(receipts)
    assert {receipt["provider"] for receipt in receipts} == {"llama_cpp"}
    assert {receipt["model"] for receipt in receipts} == {_model()}


def test_live_llama_cpp_api_wake_memory_and_replay(tmp_path: Path, monkeypatch) -> None:
    """Layer: end-to-end. The API-owned supervisor retains llama.cpp identity across iterations."""
    _configure_api(monkeypatch, db_path=tmp_path / "agent.sqlite3", catalog_path=_write_catalog(tmp_path),
                   planner=_model(), actor=_model(), critic=_model(), provider="llama_cpp")
    monkeypatch.delenv("ORKET_GOVERNED_AGENT_PROVIDER", raising=False)
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_OLLAMA_MODEL", "unused-legacy-model")
    app = create_api_app(project_root=tmp_path)
    payload = _wake_payload()
    payload["dispatch"]["request"]["admitted_capabilities"].append("memory.query")
    payload["dispatch"]["request"]["extension_config"] = {"objective_memory": True}
    with TestClient(app) as client:
        response = client.post("/v1/agent-wakes", headers=_headers(), json=payload)
        assert response.status_code == 202, response.json()
        wake = _wait_for_terminal_wake(client, response.json()["wake"]["wake_id"])
        assert wake["state"] == "completed", wake
        body = client.get("/v1/agent-runs/run-1", headers=_headers()).json()
        assert body["run"]["lifecycle_state"] == "completed", body
        receipts = _receipts(body)
        assert len(receipts) >= 6
        assert all(receipt["usage_posture"] == "measured" for receipt in receipts)
        assert {receipt["provider"] for receipt in receipts} == {"llama_cpp"}
        calls = [call for iteration in body["iterations"] for call in iteration["model_calls"]
                 if call["operation"] == "memory.query.v1"]
        assert len(calls) == 2 and all(call["status"] == "completed" for call in calls)
        replay = client.get("/v1/agent-runs/run-1/replay", headers=_headers())
        assert replay.status_code == 200 and replay.json()["status"] == "matched", replay.json()
    assert app.state.api_runtime_context.active_background_task_count == 0


@pytest.mark.parametrize("decision", ["approved", "denied"])
def test_live_llama_cpp_effect_restart(tmp_path: Path, monkeypatch, decision: str) -> None:
    """Layer: end-to-end. Real model proposals survive approval/denial and API restart."""
    _run_effect_resolution(tmp_path, monkeypatch, decision, provider="llama_cpp", model=_model())
