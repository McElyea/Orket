from __future__ import annotations

from types import SimpleNamespace

from orket.application.workflows.orchestrator import Orchestrator


def test_resolve_workflow_profile_defaults_to_legacy(monkeypatch) -> None:
    monkeypatch.delenv("ORKET_WORKFLOW_PROFILE", raising=False)
    orch = Orchestrator.__new__(Orchestrator)
    orch.org = SimpleNamespace(process_rules={})
    assert orch._resolve_workflow_profile() == "legacy_cards_v1"


def test_resolve_workflow_profile_uses_env_override(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_WORKFLOW_PROFILE", "project_task_v1")
    orch = Orchestrator.__new__(Orchestrator)
    orch.org = SimpleNamespace(process_rules={"workflow_profile": "legacy_cards_v1"})
    assert orch._resolve_workflow_profile() == "project_task_v1"


def test_resolve_workflow_profile_supports_default_switch(monkeypatch) -> None:
    monkeypatch.delenv("ORKET_WORKFLOW_PROFILE", raising=False)
    monkeypatch.setenv("ORKET_WORKFLOW_PROFILE_DEFAULT", "project_task_v1")
    orch = Orchestrator.__new__(Orchestrator)
    orch.org = SimpleNamespace(process_rules={})
    assert orch._resolve_workflow_profile() == "project_task_v1"
