import pytest

from orket.adapters.storage.async_dual_write_run_ledger import AsyncDualWriteRunLedgerRepository
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.application.services.runtime_policy import (
    resolve_gitea_worker_max_duration_seconds,
    resolve_gitea_worker_max_idle_streak,
    resolve_gitea_worker_max_iterations,
    resolve_gitea_state_pilot_enabled,
    resolve_run_ledger_mode,
    resolve_state_backend_mode,
    runtime_policy_options,
)
from orket.orchestration.engine import OrchestrationEngine


def test_state_backend_mode_policy_defaults_to_local():
    options = runtime_policy_options()
    assert options["state_backend_mode"]["default"] == "local"
    assert options["state_backend_mode"]["input_style"] == "radio"
    assert any(opt["value"] == "gitea" for opt in options["state_backend_mode"]["options"])


def test_run_ledger_mode_policy_defaults_to_sqlite():
    options = runtime_policy_options()
    assert options["run_ledger_mode"]["default"] == "sqlite"
    assert options["run_ledger_mode"]["input_style"] == "radio"
    assert any(opt["value"] == "protocol" for opt in options["run_ledger_mode"]["options"])
    assert any(opt["value"] == "dual_write" for opt in options["run_ledger_mode"]["options"])


def test_resolve_state_backend_mode_aliases():
    assert resolve_state_backend_mode("local") == "local"
    assert resolve_state_backend_mode("sqlite") == "local"
    assert resolve_state_backend_mode("gitea") == "gitea"
    assert resolve_state_backend_mode("unknown-value") == "local"


def test_resolve_run_ledger_mode_aliases():
    assert resolve_run_ledger_mode("sqlite") == "sqlite"
    assert resolve_run_ledger_mode("compat") == "sqlite"
    assert resolve_run_ledger_mode("protocol") == "protocol"
    assert resolve_run_ledger_mode("append-only") == "protocol"
    assert resolve_run_ledger_mode("dual") == "dual_write"
    assert resolve_run_ledger_mode("unknown-value") == "sqlite"


def test_resolve_gitea_state_pilot_enabled_aliases():
    assert resolve_gitea_state_pilot_enabled("enabled") is True
    assert resolve_gitea_state_pilot_enabled("true") is True
    assert resolve_gitea_state_pilot_enabled("disabled") is False
    assert resolve_gitea_state_pilot_enabled("false") is False


def test_resolve_gitea_worker_bounds():
    assert resolve_gitea_worker_max_iterations("25") == 25
    assert resolve_gitea_worker_max_iterations("-1") == 1
    assert resolve_gitea_worker_max_iterations("bad", None) == 100

    assert resolve_gitea_worker_max_idle_streak("3") == 3
    assert resolve_gitea_worker_max_idle_streak("0") == 1
    assert resolve_gitea_worker_max_idle_streak("bad", "") == 10

    assert resolve_gitea_worker_max_duration_seconds("12.5") == 12.5
    assert resolve_gitea_worker_max_duration_seconds("-1") == 0.0
    assert resolve_gitea_worker_max_duration_seconds("bad", None) == 60.0


def test_engine_rejects_gitea_state_backend_without_pilot_enablement(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_STATE_BACKEND_MODE", "gitea")
    monkeypatch.delenv("ORKET_ENABLE_GITEA_STATE_PILOT", raising=False)
    with pytest.raises(ValueError, match="requires pilot enablement"):
        OrchestrationEngine(tmp_path, config_root=tmp_path)


def test_engine_rejects_gitea_state_backend_when_readiness_is_incomplete(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_STATE_BACKEND_MODE", "gitea")
    monkeypatch.setenv("ORKET_ENABLE_GITEA_STATE_PILOT", "true")
    monkeypatch.delenv("ORKET_GITEA_URL", raising=False)
    monkeypatch.delenv("ORKET_GITEA_TOKEN", raising=False)
    monkeypatch.delenv("ORKET_GITEA_OWNER", raising=False)
    monkeypatch.delenv("ORKET_GITEA_REPO", raising=False)
    with pytest.raises(ValueError, match="pilot readiness failed"):
        OrchestrationEngine(tmp_path, config_root=tmp_path)


def test_engine_allows_gitea_state_backend_after_pilot_gate_passes(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_STATE_BACKEND_MODE", "gitea")
    monkeypatch.setenv("ORKET_ENABLE_GITEA_STATE_PILOT", "true")
    monkeypatch.setenv("ORKET_GITEA_URL", "https://gitea.local")
    monkeypatch.setenv("ORKET_GITEA_TOKEN", "secret")
    monkeypatch.setenv("ORKET_GITEA_OWNER", "acme")
    monkeypatch.setenv("ORKET_GITEA_REPO", "orket")
    engine = OrchestrationEngine(tmp_path, config_root=tmp_path)
    assert engine.state_backend_mode == "gitea"


def test_engine_defaults_run_ledger_mode_to_sqlite(monkeypatch, tmp_path):
    monkeypatch.delenv("ORKET_RUN_LEDGER_MODE", raising=False)
    engine = OrchestrationEngine(tmp_path, config_root=tmp_path)
    assert engine.run_ledger_mode == "sqlite"
    assert isinstance(engine.run_ledger, AsyncRunLedgerRepository)


def test_engine_uses_protocol_run_ledger_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    engine = OrchestrationEngine(tmp_path, config_root=tmp_path)
    assert engine.run_ledger_mode == "protocol"
    assert isinstance(engine.run_ledger, AsyncProtocolRunLedgerRepository)


def test_engine_uses_dual_write_run_ledger_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "dual_write")
    engine = OrchestrationEngine(tmp_path, config_root=tmp_path)
    assert engine.run_ledger_mode == "dual_write"
    assert isinstance(engine.run_ledger, AsyncDualWriteRunLedgerRepository)
