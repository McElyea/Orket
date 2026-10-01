from __future__ import annotations

import pytest

from orket.application.services import orchestrator_runtime_policy as orchestrator_policy

pytestmark = pytest.mark.unit


def test_resolve_workflow_profile_defaults_to_legacy(monkeypatch) -> None:
    monkeypatch.delenv("ORKET_WORKFLOW_PROFILE", raising=False)
    process_rules = {}
    assert orchestrator_policy.select_workflow_profile(process_rules=process_rules) == "legacy_cards_v1"


def test_resolve_workflow_profile_uses_env_override(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_WORKFLOW_PROFILE", "project_task_v1")
    process_rules = {"workflow_profile": "legacy_cards_v1"}
    assert orchestrator_policy.select_workflow_profile(process_rules=process_rules) == "project_task_v1"


def test_resolve_workflow_profile_supports_default_switch(monkeypatch) -> None:
    monkeypatch.delenv("ORKET_WORKFLOW_PROFILE", raising=False)
    monkeypatch.setenv("ORKET_WORKFLOW_PROFILE_DEFAULT", "project_task_v1")
    process_rules = {}
    assert orchestrator_policy.select_workflow_profile(process_rules=process_rules) == "project_task_v1"
