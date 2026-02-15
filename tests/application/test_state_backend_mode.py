import pytest

from orket.application.services.runtime_policy import (
    resolve_gitea_state_pilot_enabled,
    resolve_state_backend_mode,
    runtime_policy_options,
)
from orket.orchestration.engine import OrchestrationEngine


def test_state_backend_mode_policy_defaults_to_local():
    options = runtime_policy_options()
    assert options["state_backend_mode"]["default"] == "local"
    assert options["state_backend_mode"]["input_style"] == "radio"
    assert any(opt["value"] == "gitea" for opt in options["state_backend_mode"]["options"])


def test_resolve_state_backend_mode_aliases():
    assert resolve_state_backend_mode("local") == "local"
    assert resolve_state_backend_mode("sqlite") == "local"
    assert resolve_state_backend_mode("gitea") == "gitea"
    assert resolve_state_backend_mode("unknown-value") == "local"


def test_resolve_gitea_state_pilot_enabled_aliases():
    assert resolve_gitea_state_pilot_enabled("enabled") is True
    assert resolve_gitea_state_pilot_enabled("true") is True
    assert resolve_gitea_state_pilot_enabled("disabled") is False
    assert resolve_gitea_state_pilot_enabled("false") is False


def test_engine_rejects_gitea_state_backend_without_pilot_enablement(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_STATE_BACKEND_MODE", "gitea")
    monkeypatch.delenv("ORKET_ENABLE_GITEA_STATE_PILOT", raising=False)
    with pytest.raises(NotImplementedError, match="requires pilot enablement"):
        OrchestrationEngine(tmp_path, config_root=tmp_path)


def test_engine_rejects_gitea_state_backend_when_readiness_is_incomplete(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_STATE_BACKEND_MODE", "gitea")
    monkeypatch.setenv("ORKET_ENABLE_GITEA_STATE_PILOT", "true")
    monkeypatch.delenv("ORKET_GITEA_URL", raising=False)
    monkeypatch.delenv("ORKET_GITEA_TOKEN", raising=False)
    monkeypatch.delenv("ORKET_GITEA_OWNER", raising=False)
    monkeypatch.delenv("ORKET_GITEA_REPO", raising=False)
    with pytest.raises(NotImplementedError, match="pilot readiness failed"):
        OrchestrationEngine(tmp_path, config_root=tmp_path)


def test_engine_rejects_gitea_state_backend_after_pilot_gate_passes(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_STATE_BACKEND_MODE", "gitea")
    monkeypatch.setenv("ORKET_ENABLE_GITEA_STATE_PILOT", "true")
    monkeypatch.setenv("ORKET_GITEA_URL", "https://gitea.local")
    monkeypatch.setenv("ORKET_GITEA_TOKEN", "secret")
    monkeypatch.setenv("ORKET_GITEA_OWNER", "acme")
    monkeypatch.setenv("ORKET_GITEA_REPO", "orket")
    with pytest.raises(NotImplementedError, match="pilot gate passed, but runtime integration is still in progress"):
        OrchestrationEngine(tmp_path, config_root=tmp_path)
