from __future__ import annotations

from pathlib import Path

from orket.adapters.storage.async_dual_write_run_ledger import AsyncProtocolPrimaryRunLedgerRepository
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.runtime.run_ledger_factory import build_run_ledger_repository


def test_build_run_ledger_repository_returns_sqlite_for_sqlite_mode(tmp_path: Path) -> None:
    repo = build_run_ledger_repository(
        mode="sqlite",
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
    )
    assert isinstance(repo, AsyncRunLedgerRepository)


def test_build_run_ledger_repository_returns_protocol_for_protocol_mode(tmp_path: Path) -> None:
    repo = build_run_ledger_repository(
        mode="protocol",
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
    )
    assert isinstance(repo, AsyncProtocolRunLedgerRepository)


def test_build_run_ledger_repository_returns_dual_write_for_dual_mode(tmp_path: Path) -> None:
    repo = build_run_ledger_repository(
        mode="dual_write",
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
    )
    assert isinstance(repo, AsyncProtocolPrimaryRunLedgerRepository)
