from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.adapters.storage.async_dual_write_run_ledger import (
    AsyncDualWriteRunLedgerRepository,
    TelemetrySink,
)
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.application.services.runtime_policy import resolve_run_ledger_mode


def build_run_ledger_repository(
    *,
    mode: str,
    db_path: str | Path,
    workspace_root: str | Path,
    telemetry_sink: TelemetrySink | None = None,
    primary_mode: str = "sqlite",
) -> Any:
    resolved_mode = resolve_run_ledger_mode(mode)
    sqlite_repo = AsyncRunLedgerRepository(db_path)
    if resolved_mode == "sqlite":
        return sqlite_repo

    protocol_repo = AsyncProtocolRunLedgerRepository(Path(workspace_root))
    if resolved_mode == "protocol":
        return protocol_repo

    return AsyncDualWriteRunLedgerRepository(
        sqlite_repo=sqlite_repo,
        protocol_repo=protocol_repo,
        telemetry_sink=telemetry_sink,
        primary_mode=primary_mode,
    )
