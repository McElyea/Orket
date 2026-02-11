from types import SimpleNamespace
from pathlib import Path

from orket.orchestration.orchestrator import Orchestrator


def test_orchestrator_history_context_defaults_to_10(monkeypatch, tmp_path):
    monkeypatch.delenv("ORKET_CONTEXT_WINDOW", raising=False)
    orchestrator = Orchestrator(
        workspace=tmp_path / "workspace",
        async_cards=None,
        snapshots=None,
        org=None,
        config_root=tmp_path,
        db_path=str(tmp_path / "ctx.db"),
        loader=None,
        sandbox_orchestrator=None,
    )

    orchestrator.transcript = [
        SimpleNamespace(role=f"r{i}", content=f"c{i}") for i in range(12)
    ]
    history = orchestrator._history_context()

    assert len(history) == 10
    assert history[0] == {"role": "r2", "content": "c2"}
    assert history[-1] == {"role": "r11", "content": "c11"}


def test_orchestrator_history_context_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_CONTEXT_WINDOW", "3")
    orchestrator = Orchestrator(
        workspace=tmp_path / "workspace",
        async_cards=None,
        snapshots=None,
        org=None,
        config_root=tmp_path,
        db_path=str(tmp_path / "ctx2.db"),
        loader=None,
        sandbox_orchestrator=None,
    )

    orchestrator.transcript = [
        SimpleNamespace(role=f"r{i}", content=f"c{i}") for i in range(6)
    ]
    history = orchestrator._history_context()

    assert len(history) == 3
    assert history[0] == {"role": "r3", "content": "c3"}
