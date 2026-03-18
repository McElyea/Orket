from __future__ import annotations

from types import SimpleNamespace

import pytest

from orket.runtime.execution_pipeline import ExecutionPipeline


pytestmark = pytest.mark.unit


def test_execution_pipeline_process_rules_supports_object_style_access(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = object.__new__(ExecutionPipeline)
    pipeline.org = SimpleNamespace(
        process_rules=SimpleNamespace(
            state_backend_mode="gitea",
            run_ledger_mode="protocol",
            gitea_state_pilot_enabled="true",
            idesign_mode="architect_decides",
        )
    )
    monkeypatch.delenv("ORKET_STATE_BACKEND_MODE", raising=False)
    monkeypatch.delenv("ORKET_RUN_LEDGER_MODE", raising=False)
    monkeypatch.delenv("ORKET_ENABLE_GITEA_STATE_PILOT", raising=False)
    monkeypatch.delenv("ORKET_IDESIGN_MODE", raising=False)
    monkeypatch.setattr("orket.runtime.execution_pipeline.load_user_settings", lambda: {})

    assert pipeline._resolve_state_backend_mode() == "gitea"
    assert pipeline._resolve_run_ledger_mode() == "protocol"
    assert pipeline._resolve_gitea_state_pilot_enabled() is True
    assert pipeline._resolve_idesign_mode() == "architect_decides"
