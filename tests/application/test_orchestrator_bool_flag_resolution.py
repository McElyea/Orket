from __future__ import annotations

from types import SimpleNamespace

from orket.application.workflows.orchestrator import Orchestrator


def test_runtime_verifier_disable_flag_honors_explicit_false_env(monkeypatch) -> None:
    """Layer: contract. Verifies explicit false environment values override truthy org defaults."""
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "false")
    orch = Orchestrator.__new__(Orchestrator)
    orch.org = SimpleNamespace(process_rules={"disable_runtime_verifier": True})

    assert orch._is_runtime_verifier_disabled() is False


def test_runtime_verifier_disable_flag_honors_explicit_true_env(monkeypatch) -> None:
    """Layer: contract. Verifies explicit true environment values override false org defaults."""
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    orch = Orchestrator.__new__(Orchestrator)
    orch.org = SimpleNamespace(process_rules={"disable_runtime_verifier": False})

    assert orch._is_runtime_verifier_disabled() is True
