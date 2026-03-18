from __future__ import annotations

from orket.adapters.storage.async_dual_write_run_ledger import AsyncProtocolPrimaryRunLedgerRepository
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.runtime.execution_pipeline import ExecutionPipeline


def test_execution_pipeline_defaults_to_sqlite_run_ledger_mode(test_root, workspace, db_path, monkeypatch):
    monkeypatch.delenv("ORKET_RUN_LEDGER_MODE", raising=False)
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )
    assert pipeline.run_ledger_mode == "sqlite"
    assert isinstance(pipeline.run_ledger, AsyncRunLedgerRepository)


def test_execution_pipeline_uses_protocol_run_ledger_mode(test_root, workspace, db_path, monkeypatch):
    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )
    assert pipeline.run_ledger_mode == "protocol"
    assert isinstance(pipeline.run_ledger, AsyncProtocolRunLedgerRepository)


def test_execution_pipeline_uses_dual_write_run_ledger_mode(test_root, workspace, db_path, monkeypatch):
    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "dual_write")
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )
    assert pipeline.run_ledger_mode == "dual_write"
    assert isinstance(pipeline.run_ledger, AsyncProtocolPrimaryRunLedgerRepository)
