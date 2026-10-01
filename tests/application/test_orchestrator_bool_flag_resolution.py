from __future__ import annotations

import pytest

from orket.application.services import orchestrator_runtime_policy as orchestrator_policy

pytestmark = pytest.mark.unit


def test_runtime_verifier_disable_flag_honors_explicit_false_env(monkeypatch) -> None:
    """Layer: unit. Verifies explicit false environment values override truthy org defaults."""
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "false")
    process_rules = {"disable_runtime_verifier": True}

    assert orchestrator_policy.select_bool_flag('ORKET_DISABLE_RUNTIME_VERIFIER', 'disable_runtime_verifier', process_rules=process_rules) is False


def test_runtime_verifier_disable_flag_honors_explicit_true_env(monkeypatch) -> None:
    """Layer: unit. Verifies explicit true environment values override false org defaults."""
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    process_rules = {"disable_runtime_verifier": False}

    assert orchestrator_policy.select_bool_flag('ORKET_DISABLE_RUNTIME_VERIFIER', 'disable_runtime_verifier', process_rules=process_rules) is True
