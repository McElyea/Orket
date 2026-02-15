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


def test_engine_rejects_gitea_state_backend_until_adapter_lands(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_STATE_BACKEND_MODE", "gitea")
    with pytest.raises(NotImplementedError, match="State backend mode 'gitea' is experimental"):
        OrchestrationEngine(tmp_path, config_root=tmp_path)
